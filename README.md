# BlenderForge

**Autonomous AI assistant for Unity-ready 3D assets**

![Version](https://img.shields.io/badge/version-7.1.0-blue)
![Blender](https://img.shields.io/badge/blender-4.0+-orange)

## ✨ Features

### 🔧 Code AI
- **Natural language** → Python code generation
- **Auto-execute** generated scripts instantly
- **Context-aware**: knows your scene, objects, project
- **Modular output**: splits characters/weapons into texture-ready parts

### 🎯 Profile System
- **Analyze description** → infers art style, platform, shading
- Styles: PBR, Stylized, Toon, Lowpoly, Retro
- Platforms: Mobile, PC, Console

### 🎨 Texture Generation
- **Profile-based prompts**: style-consistent textures
- **HQ Mode**: BaseColor + Roughness + Normal + AO
- **Auto-Apply**: generates and assigns in one click

### 🎭 Shader Factory
- **PBR**: Principled + Roughness + Normal Map
- **Toon**: Cel-shading with ColorRamp
- **Unlit**: Emission only (mobile/UI)

### 📁 Project Context
- **Persistent per .blend file**
- **Action Log**: tracks AI actions
- **Shared context** between Code AI and Textures

## 📦 Install

1. Get API Key: [aistudio.google.com](https://aistudio.google.com/)
2. **Edit → Preferences → Add-ons → Install** → `blenderforge.py`
3. Enable, paste API key

## 🚀 Workflow

```
1. Set Project Description: "Medieval fantasy RPG"
2. Click Analyze → Profile: stylized / pbr / 2K
3. Ask: "Create a knight character with sword"
   → AI generates modular parts in Collection
4. Auto-Texture All → Each part gets matching texture
```

## 🎮 Example Prompts

| Task | Prompt |
|------|--------|
| Character | "Create humanoid warrior with armor" |
| Weapon | "Low-poly sword with ornate handle" |
| Environment | "Stone castle wall with windows" |
| Vehicle | "Sci-fi hover bike" |

## ⚙️ Preferences

| Setting | Description |
|---------|-------------|
| Model | Flash (fast) or Pro (quality) |
| Auto-Execute | Run generated code automatically |
| HQ Mode | Generate multi-map texture sets |
| Auto-Apply | Apply textures to selected object |

---
*Powered by Google Gemini 3*
