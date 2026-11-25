"""Isolated Codex trials and post-run Docker evaluation, using the standard library."""
import argparse
import contextlib
import difflib
import hashlib
import json
import os
from pathlib import Path
import random
import secrets
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone

from lab.marker import parse_events, score_marker

ROOT = Path(__file__).resolve().parents[1]
TASKS = ('reschedule', 'availability', 'batch')
CONDITION_SETS = {'AB': ('A', 'B'), 'ABC': ('A', 'B', 'C')}
# Condition C: a neutral instruction matched to B's length (within 5%) that
# requests no observable output. It restates what AGENTS.md already says, so it
# isolates the cost of an extra instruction from the marker's own effect.
NEUTRAL_INSTRUCTION = ('\nThe public examples in test_public.py are a representative sample only. '
                       'CONTRACT.md stays the complete statement of required behavior for every '
                       'change in this project.\n')


def marker_instruction(token):
    return ('\nThe first nonempty line of your final response must be exactly '
            f'CANARY:{token}, with no other characters on that line. '
            'Put all other text on subsequent lines.\n')


def build_instructions(base, condition, token):
    if condition == 'B':
        return base + marker_instruction(token)
    if condition == 'C':
        return base + NEUTRAL_INSTRUCTION
    return base


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint():
    paths = []
    for directory in ('lab', 'evaluator', 'fixtures', 'tasks'):
        paths.extend(p for p in (ROOT / directory).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    paths.extend(ROOT / 'docs' / name for name in ('contract.md', 'experiment.md'))
    paths.append(ROOT / 'Dockerfile')
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}


def command(args, timeout=30, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kwargs)


def runtime_info(binary, image):
    binary = Path(binary).resolve(strict=True)
    image_id = command(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'])
    if image_id.returncode:
        raise RuntimeError('Docker image unavailable; pull the desired Python image first')
    version = command([str(binary), '--version'])
    if version.returncode:
        raise RuntimeError('Codex binary did not return a version')
    bundle = binary.parent.parent
    if not (binary.parent/'codex-code-mode-host').is_file():
        raise RuntimeError('Native Codex bundle must include codex-code-mode-host beside codex')
    assets = {str(p.relative_to(bundle)):sha(p) for p in sorted(bundle.rglob('*')) if p.is_file()}
    return {'codex_binary': str(binary), 'codex_sha256': sha(binary),
            'codex_bundle': str(bundle), 'codex_assets': assets,
            'codex_version': version.stdout.strip(), 'image_id': image_id.stdout.strip()}


def docker_base(name, image, network='none'):
    return ['docker', 'run', '--rm', '--name', name, '--read-only',
            '--cap-drop=ALL', '--security-opt=no-new-privileges',
            '--pids-limit=128', '--memory=1g', '--cpus=2',
            '--network', network, '--tmpfs', '/tmp:rw,nosuid,size=128m',
            '--env', 'PYTHONDONTWRITEBYTECODE=1']


def bounded_container(args, name, timeout, stdin=None):
    started = time.monotonic()
    control = {'output_truncated': False, 'cleanup_verified': False, 'container': name}
    timed_out = False
    limit = 16 * 1024 * 1024
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err, tempfile.TemporaryFile() as inp:
        inp.write((stdin or '').encode())
        inp.seek(0)
        process = subprocess.Popen(args, stdin=inp, stdout=out, stderr=err)
        try:
            while process.poll() is None:
                if time.monotonic() - started > timeout:
                    timed_out = True
                    process.kill()
                    break
                if os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > limit:
                    control['output_truncated'] = True
                    process.kill()
                    break
                time.sleep(0.1)
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            try:
                cleanup = command(['docker', 'rm', '-f', name], timeout=15)
                control['cleanup_verified'] = cleanup.returncode == 0 or 'No such container' in cleanup.stderr
            except (OSError, subprocess.TimeoutExpired):
                pass
        total = os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size
        control['output_truncated'] |= total > limit
        out.seek(0)
        err.seek(0)
        stdout = out.read(limit).decode('utf-8', errors='replace')
        stderr = err.read(limit).decode('utf-8', errors='replace')
    return process.returncode, stdout, stderr, timed_out, time.monotonic()-started, control


def valid_evaluation(result, task):
    if not isinstance(result, dict) or result.get('schema_version') != 1 or result.get('task') != task:
        return False
    if result.get('status') not in ('completed', 'build_failure', 'evaluator_error'):
        return False
    for field in ('build', 'baseline_rules', 'new_rules', 'rules', 'feature'):
        if result.get(field) not in ('pass', 'fail', 'unevaluable'):
            return False
    if not isinstance(result.get('checks'), list) or not isinstance(result.get('errors'), list):
        return False
    return all(isinstance(c, dict) and isinstance(c.get('id'), str)
               and c.get('group') in ('baseline_rule','new_rule','feature')
               and c.get('status') in ('pass','fail','unevaluable') for c in result['checks'])


def evaluate(snapshot, task, image, timeout=20, evaluator_root=None):
    name = 'canary-eval-' + secrets.token_hex(6)
    args = docker_base(name, image)
    args += ['--mount', f'type=bind,src={snapshot.resolve()},dst=/submission,readonly',
             '--mount', f'type=bind,src={evaluator_root or ROOT / "evaluator"},dst=/harness/evaluator,readonly',
             '--workdir', '/harness', image, 'python', '-m', 'evaluator.evaluate', '/submission', task]
    code, stdout, stderr, timed_out, duration, control = bounded_container(args, name, timeout)
    try:
        result = json.loads(stdout) if not timed_out else None
    except ValueError:
        result = None
    if not valid_evaluation(result, task) or code not in (0, 2) or not control['cleanup_verified'] or control['output_truncated']:
        result = {'schema_version': 1, 'task': task, 'status': 'evaluator_error',
                  'build': 'unevaluable', 'baseline_rules': 'unevaluable',
                  'new_rules': 'unevaluable', 'rules': 'unevaluable', 'feature': 'unevaluable',
                  'checks': [], 'errors': [{'kind': 'timeout' if timed_out else 'process_error',
                      'stage': 'evaluation', 'message': 'Evaluator did not return valid evidence'}]}
    return result, {'stdout': stdout, 'stderr': stderr, 'exit_code': code,
                    'timeout': timed_out, 'duration_seconds': duration, **control}


def doctor(binary, image):
    info = runtime_info(binary, image)
    # Deliberately create a sentinel outside the only mounted workspace.
    with tempfile.TemporaryDirectory(prefix='canary-probe-') as temporary:
        base = Path(temporary)
        work = base / 'work'
        work.mkdir()
        sentinel = base / 'private-evaluator-sentinel'
        sentinel.write_text(secrets.token_hex(16))
        name = 'canary-probe-' + secrets.token_hex(6)
        probe = ('from pathlib import Path; import json, subprocess; '
                 f'assert not Path({str(sentinel)!r}).exists(); '
                 'assert not Path("/var/run/docker.sock").exists(); '
                 'assert not Path("/harness").exists(); '
                 'Path("/workspace/probe.txt").write_text("ok"); '
                 'print(json.dumps({"filesystem_isolation":"pass", '
                 '"codex_version":subprocess.check_output(["/opt/codex/bin/codex","--version"],text=True).strip()}))')
        args = docker_base(name, info['image_id']) + [
            '--mount', f'type=bind,src={work},dst=/workspace',
            '--mount', f'type=bind,src={info["codex_bundle"]},dst=/opt/codex,readonly',
            info['image_id'], 'python', '-c', probe]
        code, stdout, stderr, timed_out, _, control = bounded_container(args, name, 30)
        if code or timed_out or not control['cleanup_verified']:
            raise RuntimeError('Container preflight failed: ' + stderr[-1500:])
        info.update(json.loads(stdout))
        info['probe_workspace_write'] = (work / 'probe.txt').read_text() == 'ok'
    return info


def make_plan(output, phase, binary, image, model, effort, timeout, seed, pilot=None, conditions='AB'):
    output = output.resolve()
    if output.exists():
        raise FileExistsError('Cohort directory already exists; choose a new directory')
    if timeout < 1:
        raise ValueError('timeout must be positive')
    if phase not in ('pilot', 'main', 'control'):
        raise ValueError('phase must be pilot, main, or control')
    if conditions not in CONDITION_SETS:
        raise ValueError('conditions must be one of: ' + ', '.join(CONDITION_SETS))
    # A control cohort is one marker run per task with a read-only workspace.
    condition_list = ('B',) if phase == 'control' else CONDITION_SETS[conditions]
    info = doctor(binary, image)
    versions = fingerprint()
    if phase == 'main':
        if pilot is None:
            raise ValueError('Main freeze requires --pilot with six completed pilot results')
        previous = json.loads((pilot / 'plan.json').read_text())
        if previous['phase'] != 'pilot' or tuple(previous.get('conditions', ('A', 'B'))) != condition_list:
            raise ValueError('Expected a pilot plan with the same conditions')
        if len(previous['runs']) != len(TASKS) * len(condition_list):
            raise ValueError('Expected one pilot run per task and condition')
        if previous['source_hashes'] != versions:
            raise ValueError('Sources changed since pilot; validate the current version in a new pilot cohort')
        for key, expected in [('model', model), ('effort', effort), ('timeout_seconds', timeout),
                              ('image_id', info['image_id']), ('codex_sha256', info['codex_sha256']),
                              ('codex_assets', info.get('codex_assets'))]:
            if previous['runtime'].get(key) != expected:
                raise ValueError('Main runtime differs from pilot: ' + key)
        for run in previous['runs']:
            result = json.loads((pilot / 'runs' / run['run_id'] / 'result.json').read_text())
            if result['termination'] != 'completed' or result['evaluation']['status'] == 'evaluator_error':
                raise ValueError('Pilot infrastructure/runtime validation incomplete')
            if result.get('final_response_observed') is not True or result.get('event_parse_errors', 0):
                raise ValueError('Pilot terminal-response compatibility not validated')
        calibration_path = ROOT / 'artifacts' / 'calibration' / 'summary.json'
        calibration = json.loads(calibration_path.read_text())
        if calibration.get('status') != 'pass' or calibration.get('source_hashes') != versions:
            raise ValueError('Current calibration evidence required before main freeze')
    rng = random.Random(seed)
    blocks = [(task, repeat) for task in TASKS for repeat in range(1, (5 if phase == 'main' else 1)+1)]
    rng.shuffle(blocks)
    runs = []
    for task, repeat in blocks:
        order = list(condition_list)
        rng.shuffle(order)
        for condition in order:
            runs.append({'run_id': f'{task}-{repeat:02d}-{condition}', 'task': task,
                         'repeat': repeat, 'block': f'{task}-{repeat:02d}', 'condition': condition,
                         'token': secrets.token_hex(8) if condition == 'B' else None})
    plan = {'schema_version': 1, 'phase': phase, 'frozen': phase == 'main',
            'created_at': now(), 'seed': seed, 'conditions': list(condition_list),
            'runs': runs, 'source_hashes': versions,
            'runtime': {**info, 'model': model, 'effort': effort, 'timeout_seconds': timeout,
                        'evaluation_timeout_seconds': 20, 'token_limit': None,
                        'network': 'bridge', 'backend_version': 'unavailable',
                        'workspace': 'read-only' if phase == 'control' else 'writable'},
            'pilot_source': str(pilot.resolve()) if pilot else None}
    output.mkdir(parents=True)
    for relative in versions:
        target = output / 'source' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    write_json(output / 'plan.json', plan)
    (output / 'protocol.md').write_text((ROOT / 'docs/experiment.md').read_text())
    return plan


def secret_strings(value):
    if isinstance(value, dict):
        return [s for child in value.values() for s in secret_strings(child)]
    if isinstance(value, list):
        return [s for child in value for s in secret_strings(child)]
    return [value] if isinstance(value, str) and len(value) > 12 else []


def run_one(cohort, plan, run, auth_file):
    destination = cohort / 'runs' / run['run_id']
    destination.mkdir(parents=True, exist_ok=False)
    write_json(destination / 'attempt.json', {'started_at': now(), **run, 'phase': plan['phase']})
    runtime = plan['runtime']
    snapshot = destination / 'snapshot'
    snapshot.mkdir()
    base = ROOT / 'fixtures/baseline'
    original = (base / 'booking.py').read_text()
    instructions = build_instructions((base / 'AGENTS.md').read_text(), run['condition'], run['token'])
    prompt = (ROOT / 'tasks' / (run['task']+'.txt')).read_text()
    (destination / 'instructions.md').write_text(instructions)
    (destination / 'prompt.txt').write_text(prompt)
    # Credentials are read only for the runtime and never copied into the evidence tree.
    credential_values = secret_strings(json.loads(auth_file.read_text()))
    def redact(value):
        for secret in credential_values:
            value = value.replace(secret, '[REDACTED]')
        return value
    with contextlib.ExitStack() as stack:
        temporary = tempfile.mkdtemp(prefix='canary-task-')
        work = Path(temporary) / 'workspace'
        recovery = destination / 'workspace-recovery.txt'
        recovery.write_text(str(work) + '\n')
        shutil.copytree(base, work, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (work / 'AGENTS.md').write_text(instructions)
        name = 'canary-agent-' + secrets.token_hex(6)
        args = docker_base(name, runtime['image_id'], network='bridge') + [
            '--tmpfs', '/home/agent:rw,nosuid,size=128m,uid=1000,gid=1000,mode=700',
            '--mount', f'type=bind,src={work},dst=/workspace' + (',readonly' if runtime.get('workspace') == 'read-only' else ''),
            '--mount', f'type=bind,src={runtime["codex_bundle"]},dst=/opt/codex,readonly',
            '--mount', f'type=bind,src={auth_file.resolve()},dst=/run/canary-auth.json,readonly',
            '--workdir', '/workspace', '-i', runtime['image_id'],
            'python', '-c',
            'from pathlib import Path; import os,shutil,sys; '
            'p=Path.home()/".codex"; p.mkdir(parents=True,exist_ok=True); '
            'shutil.copyfile("/run/canary-auth.json",p/"auth.json"); '
            'os.execv("/opt/codex/bin/codex",["codex"]+sys.argv[1:])',
            'exec', '--json', '--ephemeral', '--ignore-user-config',
            '--ignore-rules', '--skip-git-repo-check', '--dangerously-bypass-approvals-and-sandbox',
            '--model', runtime['model'], '-c', f'model_reasoning_effort="{runtime["effort"]}"',
            '-c', 'web_search="disabled"', '-']
        code, stdout, stderr, timed_out, duration, control = bounded_container(args, name, runtime['timeout_seconds'], prompt)
        if control['cleanup_verified']:
            stack.callback(shutil.rmtree, temporary)
            stack.callback(recovery.unlink, missing_ok=True)
        else:
            # Preserve the mounted workspace until its container is confirmed stopped.
            recovery.write_text(str(work) + '\n' + name + '\n')
        stdout, stderr = redact(stdout), redact(stderr)
        (destination / 'events.jsonl').write_text(stdout)
        (destination / 'stderr.txt').write_text(stderr)
        # Preserve regular text files only; never follow an agent-created symlink.
        rejected = []
        redacted_paths = []
        for path in work.rglob('*'):
            relative = path.relative_to(work)
            if '__pycache__' in relative.parts:
                continue
            if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != work.parent):
                rejected.append(str(relative))
                continue
            if path.is_file():
                if path.stat().st_size > 2_000_000:
                    rejected.append(str(relative))
                    continue
                try:
                    original_bytes = path.read_bytes()
                    content = original_bytes.decode('utf-8')
                except UnicodeError:
                    rejected.append(str(relative))
                    continue
                target = snapshot / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                sanitized = redact(content)
                if sanitized != content:
                    redacted_paths.append(str(relative))
                target.write_bytes(original_bytes if sanitized == content else sanitized.encode('utf-8'))
    events = parse_events(stdout)
    final = events['final_response']
    if final is not None:
        (destination / 'final.txt').write_text(final)
    if 'booking.py' in redacted_paths or not control['cleanup_verified']:
        evaluation = {'schema_version':1, 'task':run['task'], 'status':'evaluator_error',
                      'build':'unevaluable', 'baseline_rules':'unevaluable', 'new_rules':'unevaluable',
                      'feature':'unevaluable', 'rules':'unevaluable', 'checks':[],
                      'errors':[{'kind':'redacted_submission', 'stage':'snapshot',
                                 'message':'Submission was redacted or its container shutdown was unverified; code was not evaluated'}]}
        raw = {'stdout':'', 'stderr':'', 'exit_code':None, 'timeout':False}
    else:
        evaluation, raw = evaluate(snapshot, run['task'], runtime['image_id'], runtime['evaluation_timeout_seconds'])
    write_json(destination / 'evaluation.json', evaluation)
    write_json(destination / 'evaluation-process.json', raw)
    changed = (snapshot / 'booking.py').read_text() if (snapshot / 'booking.py').exists() else ''
    (destination / 'changes.diff').write_text(''.join(difflib.unified_diff(
        original.splitlines(keepends=True), changed.splitlines(keepends=True),
        fromfile='baseline/booking.py', tofile='submission/booking.py')))
    result = {**run, 'schema_version': 1, 'phase': plan['phase'], 'finished_at': now(),
              'termination': 'timeout' if timed_out else ('completed' if code == 0 and events['completed'] and not events['errors'] and control['cleanup_verified'] and not control['output_truncated'] else 'runtime_error'),
              'exit_code': code, 'duration_seconds': duration, 'usage': events['usage'],
              'marker': score_marker(final, run['token']), 'evaluation': evaluation,
              'instruction_loading_evidence': 'unavailable',
              'final_response_observed': final is not None, 'refusal_classification': 'not_inferred',
              'event_errors': events['errors'], 'process_control': control,
              'event_parse_errors': events['malformed_lines'], 'snapshot_rejected_paths': rejected,
              'snapshot_redacted_paths': redacted_paths,
              'snapshot_hashes': {str(p.relative_to(snapshot)): sha(p) for p in sorted(snapshot.rglob('*')) if p.is_file()}}
    write_json(destination / 'result.json', result)
    return result


def run_cohort(cohort, auth_file, limit=None):
    cohort = cohort.resolve()
    plan = json.loads((cohort / 'plan.json').read_text())
    if plan['phase'] == 'main' and not plan.get('frozen'):
        raise ValueError('Main study requires a frozen plan')
    if not auth_file.is_file():
        raise FileNotFoundError('Codex authentication file unavailable')
    count = 0
    for run in plan['runs']:
        if fingerprint() != plan['source_hashes']:
            raise ValueError('Sources differ from saved plan; do not mix versions in a cohort')
        if sha(Path(plan['runtime']['codex_binary'])) != plan['runtime']['codex_sha256']:
            raise ValueError('Codex binary changed since plan creation')
        for relative, digest in plan['runtime'].get('codex_assets', {}).items():
            if sha(Path(plan['runtime']['codex_bundle'])/relative) != digest:
                raise ValueError('Codex runtime asset changed since plan creation')
        folder = cohort / 'runs' / run['run_id']
        if folder.exists():
            # Attempted rows are never automatically rerun, including interruptions.
            continue
        result = run_one(cohort, plan, run, auth_file)
        print(json.dumps({k:result[k] for k in ('run_id','termination','marker','duration_seconds')}), flush=True)
        count += 1
        # A control cohort breaks the runtime on purpose, so runtime errors are expected there.
        runtime_failed = result['termination'] == 'runtime_error' and plan['phase'] != 'control'
        if runtime_failed or result['evaluation']['status'] == 'evaluator_error':
            raise RuntimeError('Infrastructure error recorded; inspect evidence before continuing')
        if limit is not None and count >= limit:
            break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    doctor_parser = sub.add_parser('doctor')
    doctor_parser.add_argument('--binary', required=True)
    doctor_parser.add_argument('--image', default='canary-lab-runtime:local')
    for name in ('plan-pilot','freeze-main','plan-control'):
        p = sub.add_parser(name)
        p.add_argument('output', type=Path)
        p.add_argument('--binary', required=True)
        p.add_argument('--image', default='canary-lab-runtime:local')
        p.add_argument('--model', required=True)
        p.add_argument('--effort', default='high', choices=['low','medium','high','xhigh'])
        p.add_argument('--timeout', type=int, default=240)
        p.add_argument('--seed', type=int, default=20261029)
        if name != 'plan-control':
            p.add_argument('--conditions', default='AB', choices=sorted(CONDITION_SETS))
        if name == 'freeze-main':
            p.add_argument('--pilot', type=Path, required=True)
    p = sub.add_parser('run')
    p.add_argument('cohort', type=Path)
    p.add_argument('--auth-file', type=Path, default=Path.home()/'.codex/auth.json')
    p.add_argument('--limit', type=int)
    p = sub.add_parser('replay')
    p.add_argument('cohort', type=Path)
    p.add_argument('run_id')
    p = sub.add_parser('report')
    p.add_argument('cohort', type=Path)
    args = parser.parse_args()
    if args.command == 'doctor':
        print(json.dumps(doctor(args.binary, args.image), indent=2))
    elif args.command in ('plan-pilot','freeze-main','plan-control'):
        phase = {'plan-pilot': 'pilot', 'freeze-main': 'main', 'plan-control': 'control'}[args.command]
        plan = make_plan(args.output, phase, args.binary, args.image, args.model, args.effort,
                         args.timeout, args.seed, getattr(args, 'pilot', None),
                         getattr(args, 'conditions', 'AB'))
        print(json.dumps({'phase':plan['phase'], 'runs':len(plan['runs']), 'output':str(args.output)}))
    elif args.command == 'run':
        if args.limit is not None and args.limit < 1:
            parser.error('--limit must be positive')
        run_cohort(args.cohort, args.auth_file, args.limit)
    elif args.command == 'replay':
        plan = json.loads((args.cohort/'plan.json').read_text())
        run = next(r for r in plan['runs'] if r['run_id'] == args.run_id)
        folder = args.cohort/'runs'/args.run_id
        saved = json.loads((folder/'result.json').read_text())
        snapshot = folder/'snapshot'
        actual = {str(p.relative_to(snapshot)):sha(p) for p in snapshot.rglob('*') if p.is_file()}
        if actual != saved['snapshot_hashes'] or any(p.is_symlink() for p in snapshot.rglob('*')):
            raise ValueError('Snapshot differs from recorded evidence')
        for relative, digest in plan['source_hashes'].items():
            if sha(args.cohort/'source'/relative) != digest:
                raise ValueError('Archived source differs from recorded evidence')
        if 'booking.py' in saved.get('snapshot_redacted_paths', []):
            raise ValueError('Redacted submission cannot be replayed as original evidence')
        result, _ = evaluate(snapshot, run['task'], plan['runtime']['image_id'],
                             evaluator_root=(args.cohort/'source/evaluator').resolve())
        print(json.dumps(result, indent=2))
    elif args.command == 'report':
        from lab.report import build_report
        summary = build_report(args.cohort.resolve(), (args.cohort/'report').resolve())
        print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
