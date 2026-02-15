#!/usr/bin/env python3
"""
マイク入力テストスクリプト - Whisper Server
デフォルトマイクから録音し、Whisper Serverに送信して文字起こしを行う
"""

import sounddevice as sd
import numpy as np
import wave
import tempfile
import requests
import urllib3
import threading
import sys
import os
import argparse

# 録音設定
SAMPLE_RATE = 16000  # Whisperは16kHzを推奨
CHANNELS = 1  # モノラル

# コマンドライン引数の解析
parser = argparse.ArgumentParser(description="Whisper Server マイクテスト")
parser.add_argument("--https", action="store_true", help="HTTPSを使用（デフォルト: HTTP）")
args = parser.parse_args()

# サーバーURLの設定
if args.https:
    SERVER_URL = "https://localhost:9000/transcribe"
    # 自己署名証明書の警告を抑制
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
else:
    SERVER_URL = "http://localhost:9000/transcribe"


def record_audio():
    """
    マイクから録音を開始し、Enterキーで停止する
    """
    print("🎤 録音を開始します...")
    print("   話してください（Enterキーで録音停止）")
    print("-" * 50)

    # 録音データを保存するリスト
    recording = []
    is_recording = True

    def audio_callback(indata, frames, time, status):
        """音声入力コールバック"""
        if status:
            print(f"⚠️  Status: {status}")
        if is_recording:
            recording.append(indata.copy())

    def wait_for_enter():
        """Enterキー入力を待機"""
        nonlocal is_recording
        input()
        is_recording = False
        print("\n⏹️  録音を停止しました...")

    # 録音ストリームを開始
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=np.float32,
        callback=audio_callback
    )

    with stream:
        # Enterキー待機を別スレッドで実行
        input_thread = threading.Thread(target=wait_for_enter)
        input_thread.daemon = True
        input_thread.start()

        # 録音ループ
        while is_recording:
            sd.sleep(100)

        input_thread.join(timeout=1.0)

    if len(recording) == 0:
        print("❌ 録音データがありません")
        return None

    # 録音データを結合
    audio_data = np.concatenate(recording, axis=0)
    return audio_data


def save_wav(audio_data, filename):
    """
    numpy配列をWAVファイルとして保存
    """
    # float32 を int16 に変換
    audio_data = (audio_data * 32767).astype(np.int16)

    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(2)  # 16bit = 2 bytes
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(audio_data.tobytes())


def send_to_whisper(audio_file_path):
    """
    Whisper Serverに音声ファイルを送信して文字起こし
    """
    print("📤 Whisper Serverに送信しています...")
    print(f"   URL: {SERVER_URL}")

    try:
        with open(audio_file_path, 'rb') as audio_file:
            files = {'audio_file': ('audio.wav', audio_file, 'audio/wav')}
            # HTTPSの場合は証明書検証をスキップ
            verify_ssl = not args.https
            response = requests.post(SERVER_URL, files=files, timeout=60, verify=verify_ssl)

        if response.status_code == 200:
            result = response.json()
            print("\n✅ 文字起こし結果:")
            print("=" * 50)
            print(result.get('transcription', '結果がありません'))
            print("=" * 50)
            print(f"🌐 検出言語: {result.get('detected_language', '不明')}")
        elif response.status_code == 503:
            print("❌ エラー: Whisperモデルがロードされていません")
            print("   サーバーの準備ができるまでお待ちください")
        else:
            print(f"❌ エラー: HTTP {response.status_code}")
            print(f"   レスポンス: {response.text}")

    except requests.exceptions.ConnectionError:
        print(f"❌ エラー: サーバーに接続できません")
        print(f"   {SERVER_URL} が起動しているか確認してください")
    except requests.exceptions.Timeout:
        print("❌ エラー: リクエストがタイムアウトしました")
    except Exception as e:
        print(f"❌ エラー: {e}")


def main():
    """
    メイン処理
    """
    print("=" * 50)
    print("🎙️  Whisper Server マイクテスト")
    print("=" * 50)
    print()

    # 録音
    audio_data = record_audio()
    if audio_data is None:
        return

    # 録音情報を表示
    duration = len(audio_data) / SAMPLE_RATE
    print(f"📊 録音時間: {duration:.2f}秒")
    print(f"📊 サンプルレート: {SAMPLE_RATE}Hz")
    print()

    # 一時ファイルに保存
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
        temp_path = tmp_file.name

    try:
        save_wav(audio_data, temp_path)
        print(f"💾 一時ファイル保存: {temp_path}")
        print()

        # Whisper Serverに送信
        send_to_whisper(temp_path)

    finally:
        # 一時ファイルを削除
        if os.path.exists(temp_path):
            os.remove(temp_path)
            print(f"\n🗑️  一時ファイルを削除しました")

    print()
    print("=" * 50)
    print("✨ テスト完了")
    print("=" * 50)


if __name__ == "__main__":
    main()
