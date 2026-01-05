# BlenderForge

**AI with profile-based shaders for Unity-ready 3D assets**

![Version](https://img.shields.io/badge/version-6.0.0-blue)
![Blender](https://img.shields.io/badge/blender-4.0+-orange)

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎯 **Profile System** | Auto-infers style from description |
| 🎨 **Shader Factory** | PBR, Toon, Unlit materials |
| 🤖 **Autonomous Mode** | Auto-executes code |
| 📁 **Project Context** | Per .blend file |

## 📦 Install

1. Get API Key: [aistudio.google.com](https://aistudio.google.com/)
2. **Edit → Preferences → Add-ons → Install** → `blenderforge.py`
3. Enable, paste API key

## 🚀 Usage

### 1. Set Description
Examples:
- "PS1-style horror game" → lowpoly/retro
- "Stylized mobile RPG" → toon/unlit
- "AAA realistic shooter" → pbr

### 2. Analyze
Click **Analyze** → Profile extracts style/shading

### 3. Auto-Texture
Generates texture + applies matching shader:
- **PBR**: Principled + Roughness + Normal
- **Toon**: Diffuse → ShaderToRGB → ColorRamp
- **Unlit**: Emission (mobile/UI)

## 🎭 Shader Types

| Profile Shading | Blender Shader |
|-----------------|----------------|
| `pbr` | Principled BSDF |
| `toon` | Cel-shading with ColorRamp |
| `unlit` | Emission only |

---
*Powered by Google Gemini 3*
