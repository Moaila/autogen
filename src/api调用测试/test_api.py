"""
@author: 李文皓
@time: 2025/2/26
@Description: 测试openai-api脚本
问题发现：openai需要有账号，作者没有国外的信用卡，不提供服务
"""
import httpx
from openai import OpenAI

def test_openai():
    try:
        # 配置HTTP客户端
        http_client = httpx.Client(
            proxies="http://127.0.0.1:7890",
            timeout=30.0,
            http2=True
        )
        
        # 创建OpenAI客户端
        client = OpenAI(
            api_key="<填写你的api>", 
            http_client=http_client
        )
        
        # 测试API调用
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=50
        )
        print(f"请求成功！响应内容：{response.choices[0].message.content}")
        
    except Exception as e:
        print(f"请求失败：{str(e)}")
        if hasattr(e, 'response'):
            print(f"详细错误信息：{e.response.text}")

if __name__ == "__main__":
    test_openai()