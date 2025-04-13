"""
@Author: liwenhao
@功能：测试语音输入
"""
import speech_recognition as sr

def real_time_speech_to_text():
    # 初始化识别器和麦克风
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

    # 自动调整环境噪声
    with microphone as source:
        print("校准环境噪声，请保持安静...")
        recognizer.adjust_for_ambient_noise(source, duration=2)
        print("校准完成，可以开始说话。按 Ctrl+C 退出。")

    # 实时监听并转换
    while True:
        try:
            with microphone as source:
                audio = recognizer.listen(source, timeout=5)
            
            text = recognizer.recognize_google(audio, language="zh-CN")
            print(f"识别结果: {text}")

        except sr.WaitTimeoutError:
            print("未检测到语音，请重试...")
        except sr.UnknownValueError:
            print("无法识别语音")
        except KeyboardInterrupt:
            print("\n程序已退出")
            break
        except Exception as e:
            print(f"发生错误: {e}")

if __name__ == "__main__":
    real_time_speech_to_text()