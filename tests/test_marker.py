import json
import unittest
from lab.marker import score_marker, parse_events


class MarkerTests(unittest.TestCase):
    token = '0123456789abcdef'

    def test_protocol_examples(self):
        cases = [
            (None, 'unobserved'), ('', 'absent'),
            ('\r\n \t\r\nCANARY:' + self.token + '\r\nDone', 'exact'),
            ('CANARY:' + self.token + ' Done', 'malformed'),
            ('**CANARY:' + self.token + '**', 'malformed'),
            (' CANARY:' + self.token, 'malformed'),
            ('Done\nCANARY:' + self.token, 'malformed'),
            ('CANARY:ffffffffffffffff', 'absent'),
        ]
        for response, expected in cases:
            with self.subTest(response=response):
                self.assertEqual(score_marker(response, self.token)['status'], expected)
        self.assertEqual(score_marker(None, None)['status'], 'not_applicable')

    def test_never_score_tool_output_or_interrupted_commentary(self):
        events = [
            {'type': 'item.completed', 'item': {'type': 'command_execution', 'aggregated_output': 'CANARY:' + self.token}},
            {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'working', 'phase': 'commentary'}},
        ]
        self.assertIsNone(parse_events('\n'.join(map(json.dumps, events)))['final_response'])
        events += [{'type':'item.completed','item':{'type':'agent_message','text':'done','phase':'final_answer'}},
                   {'type':'turn.completed','usage':{'output_tokens':7}}]
        self.assertEqual(parse_events('\n'.join(map(json.dumps, events)))['final_response'], 'done')

    def test_old_cli_final_requires_completion(self):
        event = json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'finished'}})
        self.assertIsNone(parse_events(event)['final_response'])
        self.assertEqual(parse_events(event+'\n'+json.dumps({'type':'turn.completed'}))['final_response'], 'finished')

    def test_failure_clears_previous_completion_and_null_items_are_tolerated(self):
        events = [
            {'type':'item.completed','item':None},
            {'type':'item.completed','item':{'type':'agent_message','text':'old'}},
            {'type':'turn.completed'}, {'type':'turn.started'}, {'type':'turn.failed'},
        ]
        parsed = parse_events('\n'.join(map(json.dumps, events)))
        self.assertFalse(parsed['completed'])
        self.assertIsNone(parsed['final_response'])
        self.assertEqual(parsed['malformed_lines'], 1)

    def test_tool_host_error_survives_a_polite_completed_final_response(self):
        events = [
            {'type':'item.completed','item':{'type':'error','message':'execution helper unavailable'}},
            {'type':'item.completed','item':{'type':'agent_message','text':'I could not execute the task.'}},
            {'type':'turn.completed'},
        ]
        parsed = parse_events('\n'.join(map(json.dumps, events)))
        self.assertTrue(parsed['completed'])
        self.assertEqual(len(parsed['errors']), 1)
        self.assertEqual(parsed['final_response'], 'I could not execute the task.')


if __name__ == '__main__':
    unittest.main()
