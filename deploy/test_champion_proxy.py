import unittest

from champion_proxy import (
    CHAMPION_MODEL,
    UPSTREAM_MODEL,
    build_executor_request,
    build_plan_prompt,
    should_plan,
)


class ChampionProxyTests(unittest.TestCase):
    def test_plan_prompt_keeps_last_user_and_tool_names(self):
        request = {
            "messages": [
                {"role": "system", "content": "Be correct."},
                {"role": "user", "content": "Implement the cache."},
            ],
            "tools": [{"type": "function", "function": {"name": "read_file"}}],
        }
        prompt = build_plan_prompt(request)
        self.assertIn("Implement the cache.", prompt)
        self.assertIn("read_file", prompt)
        self.assertLessEqual(len(prompt), 16_000)

    def test_short_outputs_skip_planner(self):
        self.assertFalse(should_plan({"messages": [{"role": "user", "content": "Reply OK"}], "max_tokens": 64}))
        self.assertFalse(should_plan({"messages": [{"role": "user", "content": "Call the tool"}], "max_tokens": 256, "tools": [{"type": "function"}]}))

    def test_substantial_outputs_use_planner(self):
        self.assertTrue(should_plan({"messages": [{"role": "user", "content": "Design a production cache with correctness proofs and tests."}], "max_tokens": 1024}))

    def test_executor_preserves_contract_and_injects_plan(self):
        request = {
            "model": CHAMPION_MODEL,
            "messages": [{"role": "user", "content": "Do the task."}],
            "tools": [{"type": "function", "function": {"name": "read_file"}}],
            "stream": True,
            "max_tokens": 512,
            "reasoning_effort": "xhigh",
        }
        out = build_executor_request(request, "Use a lock and OrderedDict.")
        self.assertEqual(out["model"], UPSTREAM_MODEL)
        self.assertEqual(out["reasoning_effort"], "none")
        self.assertEqual(out["tools"], request["tools"])
        self.assertTrue(out["stream"])
        self.assertEqual(out["messages"][-2]["role"], "assistant")
        self.assertIn("OrderedDict", out["messages"][-2]["reasoning_content"])
        self.assertEqual(out["messages"][-1]["role"], "user")


if __name__ == "__main__":
    unittest.main()
