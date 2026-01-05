# BlenderForge

**AI with multi-map textures and PBR/Toon/Unlit shaders for Unity**

![Version](https://img.shields.io/badge/version-7.0.0-blue)
![Blender](https://img.shields.io/badge/blender-4.0+-orange)

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎯 **Profile System** | Auto-infers style from description |
| 🎨 **Multi-Map HQ** | BaseColor + Roughness + Normal + AO |
| 🎭 **Shader Factory** | PBR, Toon, Unlit materials |
| 🤖 **Autonomous Mode** | Auto-executes code |

## 📦 Install

1. Get API Key: [aistudio.google.com](https://aistudio.google.com/)
2. **Edit → Preferences → Add-ons → Install** → `blenderforge.py`
3. Enable, paste API key

## 🚀 Usage

### 1. Set Description
`"PS1-style horror game"` → Profile: lowpoly/retro

### 2. Analyze
Click **Analyze** → Extracts style/platform/maps

### 3. Auto-Texture
- **Fast Mode**: Single BaseColor texture
- **HQ Mode**: Full PBR set (3-4 API calls)

## 🎭 Modes

| Mode | Maps Generated | API Calls |
|------|----------------|-----------|
| Fast | BaseColor | 1 |
| HQ | Base + Rough + Normal | 3 |
| HQ+AO | Base + Rough + Normal + AO | 4 |

## 🔧 Preferences

- **HQ Mode**: Toggle multi-map generation
- **Auto-Apply**: Apply to selected object
- **Texture Size**: 1K / 2K / 4K

---
*Powered by Google Gemini 3*
