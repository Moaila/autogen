"""
@Author: DeepSeek
@Date: 2025/2/26
@Description: A simple chat demo
感谢 DeepSeek API 使用与 OpenAI 兼容的 API 格式，通过修改配置，
可以使用 OpenAI SDK 来访问 DeepSeek API，或使用与 OpenAI API 兼容的软件。
"""

from openai import OpenAI

client = OpenAI(api_key="<填写你的api>", base_url="https://api.deepseek.com")

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello"},
    ],
    stream=False # 是否启用流式对话
)

print(response.choices[0].message.content)