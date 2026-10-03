import datetime
import os
import platform
import subprocess
import sys
import psutil

class JarvisBrain:
    """
    JARVIS Assistant Core Brain
    Handles user commands, system queries, calculations, system automation, and AI logic.
    """
    def __init__(self):
        self.name = "JARVIS"

    def process_query(self, query: str) -> str:
        q = query.strip().lower()

        # Date and Time
        if any(w in q for w in ["time", "date", "day", "clock"]):
            now = datetime.datetime.now()
            return f"It is currently {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}."

        # Who is JARVIS
        if any(w in q for w in ["who are you", "who is jarvis", "what are you"]):
            return "I am JARVIS, your intelligent AI desktop assistant, upgraded with Apple Siri's liquid glow user interface."

        # System Health & Resources
        if any(w in q for w in ["system", "health", "cpu", "ram", "memory", "battery", "specs"]):
            try:
                cpu_usage = psutil.cpu_percent(interval=0.2)
                ram = psutil.virtual_memory()
                ram_used_gb = round(ram.used / (1024**3), 2)
                ram_total_gb = round(ram.total / (1024**3), 2)
                battery = psutil.sensors_battery()
                bat_str = f", Battery: {battery.percent}%" if battery else ""
                
                return (f"System Diagnostics: Operating System {platform.system()} {platform.release()}.\n"
                        f"CPU Usage: {cpu_usage}%\n"
                        f"Memory: {ram_used_gb} GB / {ram_total_gb} GB ({ram.percent}% used){bat_str}.")
            except Exception as e:
                return f"System Diagnostics: Running on {platform.system()} {platform.release()}. All core processes nominal."

        # App Launchers
        if "open chrome" in q or "launch chrome" in q:
            try:
                subprocess.Popen(["start", "chrome"], shell=True)
                return "Launching Google Chrome for you."
            except Exception:
                return "Attempted to open Google Chrome."

        if "open youtube" in q or "launch youtube" in q:
            import webbrowser
            webbrowser.open("https://www.youtube.com")
            return "Opening YouTube in your web browser."

        if "open google" in q:
            import webbrowser
            webbrowser.open("https://www.google.com")
            return "Opening Google Search."

        if "open notepad" in q:
            subprocess.Popen(["notepad.exe"])
            return "Opening Notepad."

        if "open calculator" in q or "calc" in q:
            subprocess.Popen(["calc.exe"])
            return "Opening Calculator."

        # Jokes
        if "joke" in q or "funny" in q:
            jokes = [
                "Why do programmers prefer dark mode? Because light attracts bugs!",
                "There are 10 types of people in the world: those who understand binary, and those who don't.",
                "I asked Siri if she liked working with JARVIS. She said we're a match made in the cloud!"
            ]
            import random
            return random.choice(jokes)

        # Weather simulation
        if "weather" in q:
            return "The current weather is 24°C and clear skies with a pleasant breeze."

        # Calculations
        if "calculate" in q or "math" in q or any(c in q for c in ["+", "-", "*", "/"]):
            try:
                expr = q.replace("calculate", "").replace("what is", "").replace("math", "").strip()
                allowed = "0123456789+-*/.() "
                if all(c in allowed for c in expr) and len(expr) > 0:
                    result = eval(expr)
                    return f"The calculation result for ({expr}) is {result}."
            except Exception:
                pass

        # Greetings
        if any(w in q for w in ["hi", "hello", "hey", "siri", "jarvis"]):
            return "Hello! How can I assist you today?"

        # Default Intelligent Fallback
        return f"I have processed your query: '{query}'. Is there anything specific you would like me to perform or check on your system?"
