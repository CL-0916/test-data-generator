import json
import re
import os
import requests
from typing import Dict, List, Any, Optional


class TestDataGenerator:
    """使用 DeepSeek API（requests 版）的测试数据生成器"""

    def __init__(self,
                 api_key: Optional[str] = None,
                 model: str = "deepseek-chat",
                 temperature: float = 0.7,
                 max_tokens: int = 4000):
        """
        初始化生成器

        Args:
            api_key: DeepSeek API Key，若未提供则从环境变量 DEEPSEEK_API_KEY 读取
            model: 模型名称，默认 deepseek-chat
            temperature: 生成温度，0-1之间
            max_tokens: 最大输出 token 数
        """
        # 获取 API Key
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

        prompt = f"""根据以下API接口定义，生成{count}组测试数据。

接口定义（JSON）：
{json.dumps(api_schema, indent=2, ensure_ascii=False)}

要求：
1. 需要包含以下场景的数据：{', '.join(scenarios)}
2. 每个场景至少生成{count}组数据
3. 返回格式必须是JSON，结构如下：
{{
  "test_data": [
    {{
      "scenario": "positive",
      "data": {{"field1": "value1", "field2": "value2"}},
      "description": "场景描述"
    }}
  ]
}}
4. 数据要真实、合理，符合业务逻辑
5. 如果字段有特殊约束（如邮箱、手机号），请遵守约束
6. 直接返回JSON，不要有其他说明文字

请生成："""
        return prompt

    def _call_deepseek_api(self, prompt: str) -> str:
        """调用 DeepSeek API 并返回响应内容"""
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

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
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

        # 提取JSON部分
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            return result.get("test_data", [])
        else:
            raise ValueError("无法解析返回的JSON")

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
                    # 提取接口 schema
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