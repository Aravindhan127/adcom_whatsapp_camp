import subprocess
import json

def main():
    try:
        # Run PowerShell command using json format to safely parse process details
        cmd = ["powershell", "-Command", "Get-CimInstance Win32_Process -Filter \"Name = 'ngrok.exe'\" | Select-Object ProcessId, CommandLine | ConvertTo-Json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if not result.stdout.strip():
            print("No ngrok processes found.")
            return
            
        data = json.loads(result.stdout)
        # Convert single object to list if only one process is found
        if isinstance(data, dict):
            data = [data]
            
        print("Running ngrok processes:")
        for proc in data:
            print(f"PID: {proc.get('ProcessId')}")
            print(f"Command Line: {proc.get('CommandLine')}")
            print("-" * 50)
            
    except Exception as e:
        print("Error checking ngrok processes:", e)

if __name__ == '__main__':
    main()
