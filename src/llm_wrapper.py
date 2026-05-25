"""
LLM 包装器 - 统一调用接口
支持 OpenAI / Anthropic / 本地模型
"""

import os
import json
from typing import Optional, Literal
from dataclasses import dataclass
from abc import ABC, abstractmethod

from dotenv import load_dotenv

load_dotenv()


# ============ LLM Provider 抽象 ============
class LLMProvider(ABC):
    """LLM Provider 抽象基类"""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        pass

    @abstractmethod
    def name(self) -> str:
        """提供商名称"""
        pass


# ============ OpenAI Provider ============
class OpenAIProvider(LLMProvider):
    """OpenAI GPT 系列"""

    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

        self.model = model
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self._name = "OpenAI"

    def generate(self, prompt: str, **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2000),
        )
        return response.choices[0].message.content

    def name(self) -> str:
        return f"OpenAI ({self.model})"


# ============ Anthropic Provider ============
class AnthropicProvider(LLMProvider):
    """Anthropic Claude 系列"""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: Optional[str] = None):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("请安装 anthropic: pip install anthropic")

        self.model = model
        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self._name = "Anthropic"

    def generate(self, prompt: str, **kwargs) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=kwargs.get("max_tokens", 2000),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.7),
        )
        return response.content[0].text

    def name(self) -> str:
        return f"Anthropic ({self.model})"


# ============ Local/ollama Provider ============
class LocalProvider(LLMProvider):
    """本地模型 (Ollama)"""

    def __init__(self, model: str = "qwen2.5", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self._name = f"Local ({model})"

    def generate(self, prompt: str, **kwargs) -> str:
        import requests

        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", 0.7),
                    "num_predict": kwargs.get("max_tokens", 2000),
                }
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json().get("response", "")

    def name(self) -> str:
        return self._name


# ============ DashScope Provider (阿里云) ============
class DashScopeProvider(LLMProvider):
    """阿里云 DashScope (通义千问)"""

    def __init__(
        self,
        model: str = "qwen-turbo",
        api_key: Optional[str] = None,
    ):
        self.model = model
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self._name = f"DashScope ({model})"

    def generate(self, prompt: str, **kwargs) -> str:
        import requests

        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }

        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def name(self) -> str:
        return self._name


# ============ MiniMax Provider ============
class MiniMaxProvider(LLMProvider):
    """MiniMax (海螺AI)"""

    def __init__(
        self,
        model: str = "MiniMax-Text-01",
        api_key: Optional[str] = None,
        group_id: Optional[str] = None,
    ):
        self.model = model
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY")
        self.group_id = group_id or os.getenv("MINIMAX_GROUP_ID")
        self._name = f"MiniMax ({model})"

    def generate(self, prompt: str, **kwargs) -> str:
        import requests

        url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }

        if self.group_id:
            payload["group_id"] = self.group_id

        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def name(self) -> str:
        return self._name


# ============ LLM Manager ============
@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: Literal["openai", "anthropic", "local", "dashscope", "minimax"]
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000


class LLMManager:
    """
    LLM 统一管理器

    使用方式：
    1. 自动检测环境变量创建 provider
    2. 手动指定 provider
    3. 从配置文件加载
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.provider: Optional[LLMProvider] = None
        self._fallback_provider: Optional[LLMProvider] = None

        if config:
            self._init_from_config(config)
        else:
            self._auto_detect()

    def _auto_detect(self):
        """自动检测可用的 LLM 提供商"""
        # 优先级：OpenAI > Anthropic > DashScope > MiniMax > Local

        if os.getenv("OPENAI_API_KEY"):
            try:
                self.provider = OpenAIProvider()
                print("[LLM] 使用 OpenAI")
                return
            except Exception as e:
                print(f"[LLM] OpenAI 初始化失败: {e}")

        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                self.provider = AnthropicProvider()
                print("[LLM] 使用 Anthropic Claude")
                return
            except Exception as e:
                print(f"[LLM] Anthropic 初始化失败: {e}")

        if os.getenv("DASHSCOPE_API_KEY"):
            try:
                self.provider = DashScopeProvider()
                print("[LLM] 使用阿里云 DashScope (通义千问)")
                return
            except Exception as e:
                print(f"[LLM] DashScope 初始化失败: {e}")

        if os.getenv("MINIMAX_API_KEY"):
            try:
                self.provider = MiniMaxProvider()
                print("[LLM] 使用 MiniMax (海螺AI)")
                return
            except Exception as e:
                print(f"[LLM] MiniMax 初始化失败: {e}")

        # 尝试本地 ollama
        try:
            self.provider = LocalProvider()
            print("[LLM] 使用本地模型 (Ollama)")
            return
        except Exception:
            pass

        print("[LLM] ⚠️ 未检测到任何 LLM API，将使用规则解析模式")

    def _init_from_config(self, config: LLMConfig):
        """从配置初始化"""
        if config.provider == "openai":
            self.provider = OpenAIProvider(model=config.model, api_key=config.api_key)
        elif config.provider == "anthropic":
            self.provider = AnthropicProvider(model=config.model, api_key=config.api_key)
        elif config.provider == "local":
            self.provider = LocalProvider(model=config.model, base_url=config.base_url or "http://localhost:11434")
        elif config.provider == "dashscope":
            self.provider = DashScopeProvider(model=config.model, api_key=config.api_key)
        elif config.provider == "minimax":
            self.provider = MiniMaxProvider(model=config.model, api_key=config.api_key)

    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """
        生成文本

        Args:
            prompt: 输入提示词
            **kwargs: 传递给 LLM 的额外参数

        Returns:
            生成的文本，失败返回 None
        """
        if not self.provider:
            print("[LLM] ⚠️ 没有可用的 LLM Provider")
            return None

        try:
            return self.provider.generate(prompt, **kwargs)
        except Exception as e:
            print(f"[LLM] ⚠️ 生成失败: {e}")
            return None

    def __call__(self, prompt: str, **kwargs) -> Optional[str]:
        """简写调用方式"""
        return self.generate(prompt, **kwargs)

    @property
    def name(self) -> str:
        """当前 provider 名称"""
        return self.provider.name() if self.provider else "None"


# ============ 全局单例 ============
_llm_manager: Optional[LLMManager] = None


def get_llm(config: Optional[LLMConfig] = None) -> LLMManager:
    """获取 LLM 管理器（全局单例）"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager(config)
    return _llm_manager


# ============ 快捷调用 ============
def llm_generate(prompt: str, **kwargs) -> Optional[str]:
    """快捷调用全局 LLM"""
    return get_llm().generate(prompt, **kwargs)


# ============ 测试 ============
if __name__ == "__main__":
    import sys

    print("=" * 50)
    print("LLM 包装器测试")
    print("=" * 50)

    llm = get_llm()
    print(f"当前 Provider: {llm.name}")

    # 测试调用
    test_prompt = "你好，请用一句话介绍自己。"

    if llm.provider:
        print(f"\n发送测试请求...")
        result = llm.generate(test_prompt, max_tokens=100)
        if result:
            print(f"✅ 响应: {result}")
        else:
            print("❌ 无响应")
            sys.exit(1)
    else:
        print("⚠️ 没有可用的 LLM Provider（这是正常的，如果没有配置 API key）")
        print("   简历解析将使用规则模式，不依赖 LLM")
