# BlenderForge

**AI assistant with profile-based texture generation for Unity-ready 3D assets**

![Version](https://img.shields.io/badge/version-5.0.0-blue)
![Blender](https://img.shields.io/badge/blender-4.0+-orange)

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎯 **Profile System** | Auto-infers art style from project description |
| 🎨 **Style-Aware Textures** | PBR, Stylized, Toon, Lowpoly, Retro |
| 🤖 **Autonomous Mode** | Auto-executes generated code |
| 📁 **Project Context** | Stored per .blend file |

## 📦 Install

1. Get API Key: [aistudio.google.com](https://aistudio.google.com/)
2. **Edit → Preferences → Add-ons → Install** → `blenderforge.py`
3. Enable, click ⚙️, paste API key

## 🚀 Usage

### 1. Set Project Description
Enter your project style (e.g. "PS1-style horror game" or "stylized mobile RPG")

### 2. Analyze Profile
Click **Analyze** → AI extracts:
- Art Style (PBR/Stylized/Toon/Lowpoly/Retro)
- Platform (Mobile/PC/Console)
- Shading (PBR/Toon/Unlit)
- Texture Maps (BaseColor, Roughness, Normal, AO)

### 3. Generate Textures
Auto-texture uses profile for style-consistent results

## 🎮 Profiles

| Style | Prompt Behavior |
|-------|-----------------|
| `realistic_pbr` | Seamless tileable PBR, photorealistic |
| `stylized` | Hand-painted, vibrant colors |
| `toon` | Cel-shaded, flat colors |
| `lowpoly` | Simple colors, minimal detail |
| `retro` | Pixel-art, limited palette |

---
*Powered by Google Gemini 3*
