import os
from openai import OpenAI

# 设置你的 API Key（或者从环境变量读取）
api_key = "sk-fc752843bd4f47db9b234dcbdd8fceae"

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "你是一个助手"},
        {"role": "user", "content": "你好，请回复一句话"}
    ],
    max_tokens=50
)

print(response.choices[0].message.content)