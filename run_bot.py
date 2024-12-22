import subprocess
import time

def run_bot():
    while True:
        try:
            # Run the main bot script
            subprocess.run(['python3', 'crypto_alert_bot.py'], check=True)
        except Exception as e:
            print(f"Bot crashed: {e}")
            print("Restarting in 60 seconds...")
            time.sleep(60)

if __name__ == "__main__":
    run_bot() 