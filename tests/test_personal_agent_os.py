from __future__ import annotations

import asyncio
import logging
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from fastapi.testclient import TestClient

from personal_agent_os.api import create_app
from personal_agent_os.application.factory import create_llm_config, create_runtime
from personal_agent_os.config import ConfigManager
from personal_agent_os.domain import ChatRequest, ClientCapabilities, ToolCall, ToolManifest
from personal_agent_os.infrastructure.logging import bind_log_context, clear_log_context, get_logger, setup_logging
from personal_agent_os.integrations.resona_legacy import ResonaLegacyAdapter
from personal_agent_os.llm import LLMConfig, LLMMessage, LLMTextResult
from personal_agent_os.runtime import AgentRuntime, PromptBuilder, PromptLoader
from personal_agent_os.runtime.query_parser import QueryParser
from personal_agent_os.runtime.task_planner import TaskPlanner
from personal_agent_os.skills import SkillRegistry
from personal_agent_os.tools import CapabilityGuard, FunctionToolProvider, ToolRouter


class FakeLLMClient:
    def __init__(self, text: str = "fake model response", error: Exception | None = None):
        self.text = text
        self.error = error
        self.calls = []

    async def chat(self, messages, config):
        self.calls.append((messages, config))
        if self.error:
            raise self.error
        return LLMTextResult(text=self.text, model=config.model)


class PromptAndRegistryTests(unittest.TestCase):
    def test_prompt_loader_builds_ordered_prompt(self):
        loader = PromptLoader()
        prompt = loader.build_prompt(
            agent_id="default_assistant",
            skill_ids=["memory_manager"],
            memory_context="User likes clean architecture.",
            runtime_context={"request_id": "req-1"},
        )

        self.assertIn("personal desktop Agent OS", prompt)
        self.assertIn("practical, warm personal assistant", prompt)
        self.assertIn("Memory manager skill prompt", prompt)
        self.assertIn("[Memory Context]", prompt)
        self.assertIn("Return user-facing content", prompt)

    def test_skill_registry_loads_prompt_assets(self):
        registry = SkillRegistry.from_prompts(PromptLoader().prompts_root)
        ids = {manifest.id for manifest in registry.list()}

        self.assertIn("default_assistant", ids)
        self.assertIn("memory_manager", ids)
        self.assertIn("price_compare", ids)

    def test_prompt_builder_builds_llm_messages(self):
        request = ChatRequest(query="hello builder", request_id="req-builder")
        parsed = QueryParser().parse(request.query)
        plan = TaskPlanner().plan(parsed)
        builder = PromptBuilder(PromptLoader())

        messages = builder.build_messages(
            request=request,
            plan=plan,
            routed_skills=["memory_manager"],
            memory_context="User likes concise plans.",
            runtime_context={"request_id": request.request_id},
        )

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].role, "system")
        self.assertEqual(messages[1], LLMMessage(role="user", content="hello builder"))
        self.assertIn("Memory manager skill prompt", messages[0].content)
        self.assertIn("User likes concise plans", messages[0].content)


class ToolCapabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_capability_guard_blocks_fs_write(self):
        guard = CapabilityGuard()
        manifest = ToolManifest(name="write_file", required_capabilities=["allow_fs_write"])

        blocked = guard.check(manifest, ClientCapabilities(allow_fs_write=False))

        self.assertIsNotNone(blocked)
        self.assertEqual(blocked.code, "permission_blocked")
        self.assertIn("allow_fs_write", blocked.missing_capabilities)

    async def test_tool_router_returns_structured_blocked_result(self):
        provider = FunctionToolProvider()
        provider.register(
            ToolManifest(name="write_file", required_capabilities=["allow_fs_write"]),
            lambda path, content: {"path": path, "content": content},
        )
        router = ToolRouter(providers=[provider])

        result = await router.call_tool(
            ToolCall(name="write_file", arguments={"path": "C:\\secret.txt", "content": "x"}),
            ClientCapabilities(allow_fs_write=False),
        )

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.blocked)
        self.assertEqual(result.blocked.code, "permission_blocked")


class LegacyAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_blocking_legacy_call_does_not_block_event_loop(self):
        adapter = ResonaLegacyAdapter(timeout_seconds=1.0)
        ticks = 0

        def blocking_call():
            time.sleep(0.15)
            return "done"

        async def ticker():
            nonlocal ticks
            deadline = time.time() + 0.12
            while time.time() < deadline:
                ticks += 1
                await asyncio.sleep(0.01)

        result, _ = await asyncio.gather(adapter.run_blocking(blocking_call), ticker())

        self.assertEqual(result, "done")
        self.assertGreaterEqual(ticks, 5)

    async def test_legacy_timeout_is_wrapped(self):
        adapter = ResonaLegacyAdapter(timeout_seconds=0.01)

        def slow_call():
            time.sleep(0.1)

        with self.assertRaises(TimeoutError):
            await adapter.run_blocking(slow_call, operation_name="slow_call")


class RuntimeAndApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_runtime_returns_stable_response(self):
        runtime = create_runtime()
        request = ChatRequest(query="please compare product prices", request_id="req-runtime")

        response = await runtime.run(request)

        self.assertEqual(response.request_id, "req-runtime")
        self.assertIn("Agent OS backend skeleton is running", response.message)
        self.assertTrue(response.trace_id)
        self.assertTrue(response.cards)

    async def test_agent_runtime_uses_fake_llm_when_configured(self):
        fake_llm = FakeLLMClient("real-ish model text")
        runtime = AgentRuntime(llm_client=fake_llm, llm_config=LLMConfig(model="fake/model"))
        request = ChatRequest(query="say hi", request_id="req-llm")

        response = await runtime.run(request)

        self.assertEqual(response.message, "real-ish model text")
        self.assertEqual(len(fake_llm.calls), 1)
        messages, config = fake_llm.calls[0]
        self.assertEqual(config.model, "fake/model")
        self.assertEqual(messages[-1].content, "say hi")

    async def test_agent_runtime_falls_back_when_llm_errors(self):
        fake_llm = FakeLLMClient(error=RuntimeError("network down"))
        runtime = AgentRuntime(llm_client=fake_llm, llm_config=LLMConfig(model="fake/model"))
        request = ChatRequest(query="say hi", request_id="req-llm-error")

        response = await runtime.run(request)

        self.assertIn("LLM call failed", response.message)
        self.assertIn("network down", response.message)
        self.assertIsNone(response.error)

    async def test_agent_runtime_blocks_demo_write_tool(self):
        runtime = create_runtime()
        request = ChatRequest(
            query="write a file",
            request_id="req-block",
            context={
                "demo_tool_call": {
                    "name": "demo_write_file",
                    "arguments": {"path": "C:\\secret.txt", "content": "hidden"},
                }
            },
            client_capabilities=ClientCapabilities(allow_fs_write=False),
        )

        response = await runtime.run(request)

        self.assertEqual(len(response.tool_results), 1)
        self.assertFalse(response.tool_results[0].ok)
        self.assertIsNotNone(response.tool_results[0].blocked)


class ApiContractTests(unittest.TestCase):
    def test_post_chat_contract(self):
        client = TestClient(create_app(runtime=create_runtime()))

        response = client.post("/api/chat", json={"query": "hello", "request_id": "req-api"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["request_id"], "req-api")
        self.assertIn("trace_id", payload)
        self.assertIn("cards", payload)

    def test_skills_contract(self):
        client = TestClient(create_app(runtime=create_runtime()))

        response = client.get("/api/skills")

        self.assertEqual(response.status_code, 200)
        self.assertIn("skills", response.json())

    def test_websocket_stream_contract(self):
        client = TestClient(create_app(runtime=create_runtime()))

        with client.websocket_connect("/api/chat/stream") as websocket:
            websocket.send_json({"query": "hello", "request_id": "req-ws"})
            event_types = []
            for _ in range(5):
                event = websocket.receive_json()
                event_types.append(event["type"])
                if event["type"] == "done":
                    break

        self.assertIn("thinking", event_types)
        self.assertIn("message", event_types)
        self.assertIn("done", event_types)


class ConfigManagerTests(unittest.TestCase):
    def test_defaults_only_disables_llm(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ConfigManager(project_root=Path(temp_dir))

            view = manager.load()

        self.assertFalse(view.effective.llm.enabled)
        self.assertIsNone(create_llm_config(view.effective))

    def test_local_config_enables_llm(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config" / "agent_os.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "llm": {
                            "enabled": True,
                            "active_model": "Model_Test",
                            "models": {
                                "Model_Test": {
                                    "model_name": "openai/example",
                                    "base_url": "https://example.test/v1",
                                    "api_key": "secret-key",
                                    "temperature": 0.2,
                                    "top_p": 0.8,
                                    "max_tokens": 321,
                                }
                            },
                        }
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            manager = ConfigManager(project_root=root)

            view = manager.load()
            llm_config = create_llm_config(view.effective)

        self.assertIsNotNone(llm_config)
        self.assertEqual(llm_config.model, "openai/example")
        self.assertEqual(llm_config.base_url, "https://example.test/v1")
        self.assertEqual(llm_config.api_key, "secret-key")
        self.assertEqual(llm_config.temperature, 0.2)
        self.assertEqual(llm_config.top_p, 0.8)
        self.assertEqual(llm_config.max_tokens, 321)

    def test_profile_model_name_is_normalized_for_litellm(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config" / "agent_os.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "llm": {
                            "enabled": True,
                            "active_model": "Model_2_DeepSeek",
                            "models": {"Model_2_DeepSeek": {"model_name": "deepseek-v4-flash"}},
                        }
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            manager = ConfigManager(project_root=root)

            llm_config = create_llm_config(manager.load().effective)

        self.assertIsNotNone(llm_config)
        self.assertEqual(llm_config.model, "deepseek/deepseek-v4-flash")

    def test_env_override_affects_effective_not_persisted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config" / "agent_os.yaml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "llm": {
                            "enabled": True,
                            "active_model": "Model_Test",
                            "models": {
                                "Model_Test": {
                                    "model_name": "openai/local",
                                    "api_key": "local-key",
                                }
                            },
                        }
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            manager = ConfigManager(project_root=root)

            with patch.dict(
                "os.environ",
                {
                    "AGENT_OS_MODEL": "openai/env",
                    "AGENT_OS_API_KEY": "env-key",
                    "AGENT_OS_TEMPERATURE": "0.9",
                    "AGENT_OS_TOP_P": "0.7",
                    "AGENT_OS_MAX_TOKENS": "999",
                },
            ):
                view = manager.load()

        persisted_profile = view.persisted.llm.models["Model_Test"]
        effective_profile = view.effective.llm.models["Model_Test"]
        self.assertEqual(persisted_profile.model_name, "openai/local")
        self.assertEqual(persisted_profile.api_key, "local-key")
        self.assertEqual(effective_profile.model_name, "openai/env")
        self.assertEqual(effective_profile.api_key, "env-key")
        self.assertEqual(effective_profile.temperature, 0.9)
        self.assertEqual(effective_profile.top_p, 0.7)
        self.assertEqual(effective_profile.max_tokens, 999)
        self.assertIn("llm.models.Model_Test.model_name", view.env_overrides)
        self.assertIn("llm.models.Model_Test.api_key", view.env_overrides)

    def test_safe_dict_masks_api_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = ConfigManager(project_root=root)
            view = manager.save_patch(
                {
                    "llm": {
                        "active_model": "Model_Test",
                        "models": {"Model_Test": {"api_key": "super-secret", "model_name": "openai/example"}},
                    }
                }
            )

            safe = view.to_safe_dict()

        self.assertEqual(safe["persisted"]["llm"]["models"]["Model_Test"]["api_key"], "********")
        self.assertNotIn("super-secret", str(safe))

    def test_patch_rejects_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ConfigManager(project_root=Path(temp_dir))

            with self.assertRaises(ValueError):
                manager.save_patch({"llm": {"unknown": "nope"}})


class ConfigApiTests(unittest.TestCase):
    def test_get_config_masks_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = ConfigManager(project_root=root)
            manager.save_patch(
                {
                    "llm": {
                        "active_model": "Model_Test",
                        "models": {"Model_Test": {"api_key": "secret-key", "model_name": "openai/example"}},
                    }
                }
            )
            client = TestClient(create_app(project_root=root))

            response = client.get("/api/config")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["persisted"]["llm"]["models"]["Model_Test"]["api_key"], "********")
        self.assertNotIn("secret-key", str(payload))

    def test_patch_config_saves_and_swaps_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app = create_app(project_root=root)
            old_runtime = app.state.runtime
            client = TestClient(app)

            response = client.patch(
                "/api/config",
                json={
                    "llm": {
                        "enabled": True,
                        "active_model": "Model_Test",
                        "models": {"Model_Test": {"model_name": "openai/example", "api_key": "secret-key"}},
                    }
                },
            )

            config_data = yaml.safe_load((root / "config" / "agent_os.yaml").read_text(encoding="utf-8"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNot(app.state.runtime, old_runtime)
        self.assertEqual(config_data["llm"]["enabled"], True)
        self.assertEqual(config_data["llm"]["active_model"], "Model_Test")
        self.assertEqual(config_data["llm"]["models"]["Model_Test"]["model_name"], "openai/example")
        self.assertEqual(response.json()["persisted"]["llm"]["models"]["Model_Test"]["api_key"], "********")

    def test_patch_config_rejects_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            client = TestClient(create_app(project_root=Path(temp_dir)))

            response = client.patch("/api/config", json={"llm": {"unknown": "nope"}})

        self.assertEqual(response.status_code, 400)


class LLMClientBoundaryTests(unittest.TestCase):
    def test_litellm_client_does_not_import_runtime_prompt_or_tools(self):
        import personal_agent_os.llm.litellm_client as litellm_client

        source = Path(litellm_client.__file__).read_text(encoding="utf-8")
        self.assertNotIn("PromptBuilder", source)
        self.assertNotIn("PromptLoader", source)
        self.assertNotIn("ToolRouter", source)
        self.assertNotIn("AgentRuntime", source)
        self.assertNotIn("StructuredOutput", source)


class LoggingTests(unittest.TestCase):
    def test_logging_includes_trace_and_sanitizes_sensitive_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            setup_logging(root, timestamp="test")
            tokens = bind_log_context(trace_id="trace-123", request_id="req-123", tool_call_id="tool-123")
            try:
                logger = get_logger("runtime")
                logger.info(
                    "api_key=%s path=%s image=%s [User IP: 1.2.3.4]",
                    "sk-secret-secret-secret",
                    "C:\\Users\\Alice\\secret.txt",
                    "data:image/png;base64," + "A" * 120,
                )
            finally:
                clear_log_context(tokens)

            logging.shutdown()
            content = (root / "logs" / "test" / "runtime.log").read_text(encoding="utf-8")

        self.assertIn("trace-123", content)
        self.assertIn("req-123", content)
        self.assertIn("tool-123", content)
        self.assertNotIn("sk-secret-secret-secret", content)
        self.assertNotIn("C:\\Users\\Alice", content)
        self.assertNotIn("1.2.3.4", content)
        self.assertIn("[BASE64_IMAGE_REDACTED]", content)


if __name__ == "__main__":
    unittest.main()
