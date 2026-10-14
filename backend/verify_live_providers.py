#!/usr/bin/env python3
"""
LearnMate AI - Multi-Provider Live Connectivity Verification Script
Tests actual live API connectivity for configured providers without exposing secrets:
- Google Gemini (gemini-3.8-flash)
- GroqCloud (llama-3.3-70b-versatile)
- NVIDIA Nemotron (nvidia/llama-3.1-nemotron-70b-instruct)

Usage:
    python backend/verify_live_providers.py
"""
import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

def mask_secret(val: str) -> str:
    if not val:
        return "[NOT SET]"
    if len(val) <= 8:
        return "[CONFIGURED]"
    return val[:4] + "..." + val[-4:]

def main():
    print("=" * 70)
    print("  LearnMate AI - Multi-Provider Live Verification")
    print("=" * 70)

    from app.core.config import settings
    from app.core.ai_provider import get_ai_provider, reset_provider_cache
    from app.core.gemini import gemini_service

    print(f"Active Provider (AI_PROVIDER) : {settings.AI_PROVIDER}")
    print(f"Gemini Key Present            : {bool(settings.GEMINI_API_KEY)} ({mask_secret(settings.GEMINI_API_KEY)})")
    print(f"Groq Key Present              : {bool(settings.GROQ_API_KEY)} ({mask_secret(settings.GROQ_API_KEY)})")
    print(f"NVIDIA Key Present            : {bool(settings.NVIDIA_API_KEY)} ({mask_secret(settings.NVIDIA_API_KEY)})")
    print("-" * 70)

    # 1. Test Groq Live
    print("\n[Test 1/3] Testing GroqCloud Live Connectivity...")
    if not settings.GROQ_API_KEY:
        print("  -> SKIPPED: GROQ_API_KEY is not set in backend/.env")
    else:
        try:
            groq_p = get_ai_provider("groq")
            res = groq_p.test_connectivity()
            if res.get("verified"):
                print(f"  -> SUCCESS! Model: {res.get('model')}")
                print(f"  -> Sample Response: {res.get('sample_generation', '').strip()}")
            else:
                print(f"  -> FAILED: {res.get('error') or res.get('message')}")
        except Exception as e:
            print(f"  -> EXCEPTION: {e}")

    # 2. Test NVIDIA Nemotron Live
    print("\n[Test 2/3] Testing NVIDIA Nemotron Live Connectivity...")
    if not settings.NVIDIA_API_KEY:
        print("  -> SKIPPED: NVIDIA_API_KEY is not set in backend/.env")
    else:
        try:
            nvidia_p = get_ai_provider("nvidia")
            res = nvidia_p.test_connectivity()
            if res.get("verified"):
                print(f"  -> SUCCESS! Model: {res.get('model')}")
                print(f"  -> Sample Response: {res.get('sample_generation', '').strip()}")
            else:
                print(f"  -> FAILED: {res.get('error') or res.get('message')}")
        except Exception as e:
            print(f"  -> EXCEPTION: {e}")

    # 3. Test Gemini Live
    print("\n[Test 3/3] Testing Google Gemini Live Connectivity...")
    if not settings.GEMINI_API_KEY:
        print("  -> SKIPPED: GEMINI_API_KEY is not set in backend/.env")
    else:
        try:
            gem_p = get_ai_provider("gemini")
            res = gem_p.test_connectivity()
            if res.get("verified"):
                print(f"  -> SUCCESS! Model: {res.get('model')}")
                print(f"  -> Sample Response: {res.get('sample_generation', '').strip()}")
            else:
                print(f"  -> FAILED/QUOTA: {res.get('error') or res.get('message')}")
        except Exception as e:
            print(f"  -> EXCEPTION: {e}")

    print("\n" + "=" * 70)
    print("  Verification Complete.")
    print("=" * 70)

if __name__ == "__main__":
    main()
