import json
import os
import requests
import time
from typing import Dict, List, Any, Optional

class TestDataGenerator:
    """使用 DeepSeek API（requests 版）的测试数据生成器"""

    def __init__(self,
                 api_key: Optional[str] = None,
                 model: str = "deepseek-chat",
                 temperature: float = 1.0,
                 max_tokens: int = 4000):
        """
        初始化生成器

        Args:
            api_key: DeepSeek API Key，若未提供则从环境变量 DEEPSEEK_API_KEY 读取
            model: 模型名称，默认 deepseek-chat
            temperature: 生成温度，0-1之间
            max_tokens: 最大输出 token 数
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("请提供 DeepSeek API Key 或设置环境变量 DEEPSEEK_API_KEY")

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_url = "https://api.deepseek.com/v1/chat/completions"

    def _build_prompt(self, api_schema: Dict, count: int = 10,
                      scenarios: List[str] = None) -> str:
        """构建提示词"""
        if scenarios is None:
            scenarios = ["positive", "boundary", "negative"]

        prompt = f"""你是一个测试数据生成专家。请根据以下API定义，生成测试数据。
API定义（JSON）：
{json.dumps(api_schema, indent=2, ensure_ascii=False)}

要求：
1. 生成{count}组测试数据，场景包括：{', '.join(scenarios)}。
2. **只返回一个 JSON 对象，不要包含任何解释、注释或额外文字。**
3. JSON 结构必须为：
{{
  "test_data": [
    {{"scenario": "positive", "data": {{...}}, "description": "..."}}
  ]
}}
请直接输出 JSON："""
        return prompt

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从文本中提取第一个完整的 JSON 对象（支持嵌套）"""
        # 先尝试直接解析整个文本
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 方法1：找到第一个 '{' 和与之匹配的 '}'
        stack = []
        start = None
        for i, ch in enumerate(text):
            if ch == '{':
                if not stack:
                    start = i
                stack.append(ch)
            elif ch == '}':
                if stack:
                    stack.pop()
                    if not stack:
                        json_str = text[start:i+1]
                        try:
                            return json.loads(json_str)
                        except json.JSONDecodeError:
                            # 继续寻找下一个
                            start = None
                            continue
        # # 方法2：使用正则（备选，适用于简单情况）
        # match = re.search(r'\{[^{}]*\}', text)
        # if match:
        #     try:
        #         return json.loads(match.group())
        #     except json.JSONDecodeError:
        #         pass
        # raise ValueError("无法从返回内容中提取有效的 JSON")

    def _call_deepseek_api(self, prompt: str) -> str:
        """调用 DeepSeek API 并返回响应内容，支持超时重试"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一个专业的测试数据生成专家，精通API测试。请严格按照JSON格式返回结果。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        max_retries = 3
        retry_delay = 2  # 秒
        timeout_seconds = 90

        for attempt in range(max_retries):
            try:
                print(f"[DEBUG] 正在调用 DeepSeek API，第 {attempt+1} 次尝试...")
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=timeout_seconds
                )
                print(f"[DEBUG] 状态码: {response.status_code}")
                if response.status_code != 200:
                    print(f"[DEBUG] 错误响应内容: {response.text[:300]}")
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                print(f"[DEBUG] 返回内容长度: {len(content)}")
                return content

            except requests.exceptions.Timeout:
                print(f"[WARN] 请求超时 (第 {attempt+1} 次)")
                if attempt < max_retries - 1:
                    print(f"[INFO] 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise Exception(f"API 请求超时，已重试 {max_retries} 次，请稍后再试")

            except requests.exceptions.RequestException as e:
                raise Exception(f"API 请求失败: {str(e)}")

            except (KeyError, IndexError) as e:
                raise Exception(f"响应格式异常: {str(e)}")

    def generate(self, api_schema: Dict, count: int = 10,
                 scenarios: List[str] = None) -> List[Dict]:
        """
        生成测试数据

        Args:
            api_schema: API 接口定义的字典
            count: 每个场景生成的数据数量
            scenarios: 场景列表，如 ["positive", "boundary", "negative"]

        Returns:
            测试数据列表，每个元素包含 scenario, data, description
        """
        prompt = self._build_prompt(api_schema, count, scenarios)
        content = self._call_deepseek_api(prompt)

        # 打印前500字符便于调试
        print(f"[DEBUG] API 返回原始内容（前500字符）: {content[:500]}")

        try:
            result = self._extract_json(content)
            return result.get("test_data", [])
        except Exception as e:
            # 抛出更详细的错误，包含原始内容片段
            raise Exception(f"JSON解析失败: {str(e)}。原始返回内容: {content[:300]}")

    def generate_for_swagger(self, swagger_url: str, count: int = 10) -> Dict[str, List]:
        """
        从 Swagger 文档生成所有接口的测试数据

        Args:
            swagger_url: Swagger JSON 文件的 URL
            count: 每个接口每个场景生成的数据数量

        Returns:
            字典，键为 "METHOD path"，值为测试数据列表
        """
        resp = requests.get(swagger_url)
        resp.raise_for_status()
        swagger = resp.json()

        results = {}
        for path, methods in swagger.get("paths", {}).items():
            for method, details in methods.items():
                if method.lower() in ["get", "post", "put", "delete", "patch"]:
                    schema = {
                        "path": path,
                        "method": method.upper(),
                        "parameters": details.get("parameters", []),
                        "requestBody": details.get("requestBody", {}),
                        "responses": details.get("responses", {})
                    }
                    try:
                        test_data = self.generate(schema, count)
                        results[f"{method.upper()} {path}"] = test_data
                    except Exception as e:
                        results[f"{method.upper()} {path}"] = {"error": str(e)}
        return results

    def export_formats(self, test_data: List[Dict], format: str = "json") -> str:
        """
        导出不同格式的测试数据

        Args:
            test_data: 测试数据列表
            format: 导出格式，支持 json, csv, pytest, postman

        Returns:
            格式化后的字符串
        """
        if format == "json":
            return json.dumps(test_data, indent=2, ensure_ascii=False)

        elif format == "csv":
            import pandas as pd
            rows = []
            for item in test_data:
                row = {"scenario": item["scenario"], "description": item["description"]}
                row.update(item["data"])
                rows.append(row)
            df = pd.DataFrame(rows)
            return df.to_csv(index=False)

        elif format == "pytest":
            code = "import pytest\n\n\n"
            for i, item in enumerate(test_data):
                code += f"def test_case_{i}():\n"
                code += f'    """{item["description"]}"""\n'
                code += f"    data = {json.dumps(item['data'], indent=2)}\n"
                code += "    # TODO: 替换为你的 API 调用\n"
                code += "    # response = client.post('/your/endpoint', json=data)\n"
                code += "    # assert response.status_code == 200\n\n"
            return code

        elif format == "postman":
            collection = {
                "info": {
                    "name": "AI Generated Test Data",
                    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
                },
                "item": []
            }
            for item in test_data:
                request = {
                    "name": item["description"],
                    "request": {
                        "method": "POST",
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps(item["data"], indent=2)
                        },
                        "url": "{{base_url}}/your/endpoint"
                    }
                }
                collection["item"].append(request)
            return json.dumps(collection, indent=2)

        else:
            raise ValueError(f"不支持的导出格式: {format}")