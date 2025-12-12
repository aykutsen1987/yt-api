"""
Test script for YouTube to MP3/M4A Converter API
"""

import requests
import json
from typing import Dict, Any

# ============================================
# CONFIGURATION
# ============================================

# ✅ RENDER URL'nizi buraya yazın
BASE_URL = "https://yt-api-6cp1.onrender.com"  # Kendi URL'nizi kullanın
# Local test için: BASE_URL = "http://localhost:8000"

# ✅ Test YouTube URLs
TEST_URLS = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
    "https://www.youtube.com/watch?v=9bZkp7q19f0",  # PSY - GANGNAM STYLE
]

# ============================================
# TEST FUNCTIONS
# ============================================

def test_health_check():
    """Test /health endpoint"""
    print("\n🧪 Testing /health endpoint...")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed")
            print(f"   Status: {data.get('status')}")
            print(f"   FFmpeg: {data.get('ffmpeg')}")
            print(f"   System: {data.get('system')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_root():
    """Test / endpoint"""
    print("\n🧪 Testing / endpoint...")
    
    try:
        response = requests.get(BASE_URL, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Root endpoint passed")
            print(f"   Name: {data.get('name')}")
            print(f"   Version: {data.get('version')}")
            return True
        else:
            print(f"❌ Root endpoint failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Root endpoint error: {e}")
        return False

def test_convert(url: str, format: str = "mp3", quality: str = "best") -> bool:
    """Test /api/yt endpoint"""
    print(f"\n🧪 Testing conversion: {url}")
    print(f"   Format: {format}, Quality: {quality}")
    
    try:
        payload = {
            "url": url,
            "format": format,
            "quality": quality
        }
        
        response = requests.post(
            f"{BASE_URL}/api/yt",
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Conversion successful")
            print(f"   Title: {data.get('title')}")
            print(f"   Duration: {data.get('duration')}s")
            print(f"   Audio URL: {data.get('audio')[:100]}...")
            print(f"   Uploader: {data.get('uploader')}")
            return True
        else:
            print(f"❌ Conversion failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ Conversion timeout (>60s)")
        return False
    except Exception as e:
        print(f"❌ Conversion error: {e}")
        return False

def test_invalid_url():
    """Test with invalid URL"""
    print("\n🧪 Testing invalid URL...")
    
    try:
        payload = {
            "url": "https://invalid-url.com/video",
            "format": "mp3"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/yt",
            json=payload,
            timeout=30
        )
        
        if response.status_code >= 400:
            print(f"✅ Invalid URL correctly rejected: {response.status_code}")
            return True
        else:
            print(f"❌ Invalid URL should have been rejected")
            return False
            
    except Exception as e:
        print(f"❌ Invalid URL test error: {e}")
        return False

def test_invalid_format():
    """Test with invalid format"""
    print("\n🧪 Testing invalid format...")
    
    try:
        payload = {
            "url": TEST_URLS[0],
            "format": "invalid_format"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/yt",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 422:  # Validation error
            print(f"✅ Invalid format correctly rejected: {response.status_code}")
            return True
        else:
            print(f"❌ Invalid format should have been rejected")
            return False
            
    except Exception as e:
        print(f"❌ Invalid format test error: {e}")
        return False

# ============================================
# MAIN TEST RUNNER
# ============================================

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("🚀 YouTube to MP3/M4A Converter API - Test Suite")
    print("=" * 60)
    print(f"📍 Base URL: {BASE_URL}")
    
    results = []
    
    # Test 1: Root endpoint
    results.append(("Root Endpoint", test_root()))
    
    # Test 2: Health check
    results.append(("Health Check", test_health_check()))
    
    # Test 3: Valid conversion (MP3)
    results.append(("Convert to MP3", test_convert(TEST_URLS[0], "mp3", "best")))
    
    # Test 4: Valid conversion (M4A)
    results.append(("Convert to M4A", test_convert(TEST_URLS[0], "m4a", "192")))
    
    # Test 5: Invalid URL
    results.append(("Invalid URL", test_invalid_url()))
    
    # Test 6: Invalid format
    results.append(("Invalid Format", test_invalid_format()))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return True
    else:
        print(f"⚠️ {total - passed} test(s) failed")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
