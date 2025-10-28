#!/usr/bin/env python3
# Demonstrates the flow end-to-end.
import os
from main import main

if __name__ == "__main__":
    print("=== DEMO: rules ===")
    os.system("python main.py --demo rules")

    print("\n=== DEMO: langchain1 ===")
    os.system("python main.py --demo langchain1")

    print("\n=== DEMO: langchain2 ===")
    os.system("python main.py --demo langchain2")

    print("\n=== DEMO: simple_agents ===")
    os.system("python main.py --demo simple_agents")

    print("\n=== DEMO: autogen ===")
    os.system("python main.py --demo autogen")

    print("\n=== DEMO: hybrid ===")
    os.system("python main.py --demo hybrid")
