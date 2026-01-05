import bpy
import textwrap
import threading
import re
import json
import urllib.request
import urllib.error
import ssl
import base64
import os
import tempfile

bl_info = {
    "name": "BlenderForge",
    "blender": (4, 0),
    "category": "Object",
    "version": (3, 0, 0),
    "author": "usexless",
    "description": "Autonomous AI assistant with texture generation for Unity-ready 3D assets",
}

# =============================================================================
# Global state (session only - project context stored in Scene)
# =============================================================================
_chat_history = []
_status = "⚪ Ready"
_model_info = ""
_stop_requested = False
_last_activity = ""
_texture_path = ""
_history_index = -1  # Current position in response history

# =============================================================================
# Preferences
# =============================================================================

class ForgePreferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    
    api_key: bpy.props.StringProperty(
        name="API Key",
        description="Gemini API Key from aistudio.google.com",
        default="",
        subtype='PASSWORD'
    )
    
    model: bpy.props.EnumProperty(
        name="Model",
        items=[
            ('gemini-3-flash-preview', "⚡ Flash", "Fast ($0.50/M)"),
            ('gemini-3-pro-preview', "🧠 Pro", "Smart ($2/M)"),
        ],
        default='gemini-3-flash-preview'
    )
    
    auto_execute: bpy.props.BoolProperty(
        name="Auto-Execute",
        description="Automatically run generated code",
        default=True
    )
    
    texture_size: bpy.props.EnumProperty(
        name="Texture Size",
        items=[
            ('1K', "1K", "1024x1024"),
            ('2K', "2K", "2048x2048"),
            ('4K', "4K", "4096x4096"),
        ],
        default='2K'
    )
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "api_key")
        layout.prop(self, "model")
        layout.prop(self, "auto_execute")
        layout.prop(self, "texture_size")
        layout.separator()
        layout.label(text=f"Status: {_status}")


def get_key():
    p = bpy.context.preferences.addons.get(__name__)
    return p.preferences.api_key if p else ""

def get_model():
    p = bpy.context.preferences.addons.get(__name__)
    return p.preferences.model if p else "gemini-3-flash-preview"

def is_auto():
    p = bpy.context.preferences.addons.get(__name__)
    return p.preferences.auto_execute if p else True

def get_texture_size():
    p = bpy.context.preferences.addons.get(__name__)
    return p.preferences.texture_size if p else "2K"

def model_name():
    m = get_model()
    return "⚡Flash" if "flash" in m else "🧠Pro"


# =============================================================================
# Project Context (stored in Scene - persists with .blend file)
# =============================================================================

def get_project_log(scene):
    """Get project log from scene (JSON stored in string property)."""
    try:
        log_str = scene.forge_project_log
        if log_str:
            return json.loads(log_str)
    except:
        pass
    return []


def set_project_log(scene, log_list):
    """Save project log to scene."""
    scene.forge_project_log = json.dumps(log_list[-50:])  # Keep max 50


def log_action(action):
    """Add action to project log (stored in current scene)."""
    try:
        scene = bpy.context.scene
        log = get_project_log(scene)
        log.append(action)
        set_project_log(scene, log)
    except:
        pass


def get_response_history(scene):
    """Get response history from scene."""
    try:
        hist_str = scene.forge_response_history
        if hist_str:
            return json.loads(hist_str)
    except:
        pass
    return []


def set_response_history(scene, history):
    """Save response history to scene."""
    scene.forge_response_history = json.dumps(history[-20:])  # Keep max 20


def add_to_history(scene, response, code):
    """Add response to history."""
    global _history_index
    history = get_response_history(scene)
    history.append({"response": response, "code": code})
    set_response_history(scene, history)
    _history_index = len(history) - 1


# =============================================================================
# Status
# =============================================================================

def set_status(s, activity=""):
    global _status, _last_activity
    _status = s
    if activity:
        _last_activity = activity


# =============================================================================
# Code Generation API
# =============================================================================

def call_api(messages, system=None):
    global _status, _model_info, _stop_requested
    
    key = get_key()
    if not key:
        log_action("[ERROR] No API key configured")
        raise Exception("No API Key - Set it in Preferences")
    
    if _stop_requested:
        raise Exception("Stopped by user")
    
    model = get_model()
    _model_info = model_name()
    set_status(f"🔄 {_model_info} thinking...", "Sending request")
    
    version = "v1alpha" if "preview" in model else "v1beta"
    url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={key}"
    
    payload = {"contents": messages, "generationConfig": {"temperature": 0.7, "maxOutputTokens": 8192}}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        
        set_status(f"🔄 {_model_info} generating...", "Waiting for response")
        
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=90) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            
            # Check for safety blocks
            if 'promptFeedback' in result:
                block = result['promptFeedback'].get('blockReason')
                if block:
                    log_action(f"[ERROR] Content blocked: {block}")
                    raise Exception(f"Content blocked: {block}")
            
            if 'candidates' in result and result['candidates']:
                candidate = result['candidates'][0]
                
                # Check finish reason
                finish = candidate.get('finishReason', '')
                if finish == 'SAFETY':
                    log_action("[ERROR] Response blocked by safety filter")
                    raise Exception("Response blocked by safety filter")
                
                text = candidate.get('content', {}).get('parts', [{}])[0].get('text', '')
                set_status(f"✅ {_model_info} done", "Response received")
                return text
            
            log_action("[ERROR] Empty response from API")
            set_status(f"⚠️ Empty response", "No content")
            return ""
            
    except urllib.error.HTTPError as e:
        error_details = parse_api_error(e)
        log_action(f"[ERROR] HTTP {e.code}: {error_details['message']}")
        set_status(f"❌ {error_details['status']}", error_details['message'][:30])
        raise Exception(error_details['message'])
    
    except urllib.error.URLError as e:
        log_action(f"[ERROR] Network: {str(e.reason)}")
        set_status("❌ Network Error", str(e.reason)[:30])
        raise Exception(f"Network error: {e.reason}")
    
    except json.JSONDecodeError as e:
        log_action(f"[ERROR] Invalid JSON response")
        set_status("❌ Parse Error", "Invalid response")
        raise Exception("Invalid API response format")


def parse_api_error(e):
    """Parse HTTP error into detailed info."""
    try:
        body = e.read().decode('utf-8') if e.fp else ""
        error_json = json.loads(body) if body else {}
        msg = error_json.get('error', {}).get('message', '')
        code = error_json.get('error', {}).get('code', e.code)
    except:
        msg = ""
        code = e.code
    
    # Human-readable error messages
    if e.code == 400:
        if 'API_KEY' in msg.upper() or 'key' in msg.lower():
            return {"status": "Invalid Key", "message": "API key is invalid - get new one at aistudio.google.com"}
        elif 'model' in msg.lower():
            return {"status": "Model Error", "message": f"Model not available: {msg[:50]}"}
        else:
            return {"status": f"Bad Request", "message": msg[:80] or "Invalid request"}
    elif e.code == 401:
        return {"status": "Unauthorized", "message": "API key unauthorized - check permissions"}
    elif e.code == 403:
        return {"status": "Forbidden", "message": "Access denied - enable Generative AI API in Google Cloud"}
    elif e.code == 404:
        return {"status": "Not Found", "message": "Model not found - try different model in Preferences"}
    elif e.code == 429:
        return {"status": "Rate Limited", "message": "Too many requests - wait 1 minute and try again"}
    elif e.code == 500:
        return {"status": "Server Error", "message": "Google API server error - try again later"}
    elif e.code == 503:
        return {"status": "Unavailable", "message": "Service temporarily unavailable"}
    else:
        return {"status": f"HTTP {e.code}", "message": msg[:80] or f"HTTP error {e.code}"}


# =============================================================================
# Texture Generation API (Nano Banana Pro)
# =============================================================================

def generate_texture(prompt, size="2K"):
    global _stop_requested, _texture_path
    
    key = get_key()
    if not key:
        raise Exception("No API Key")
    
    if _stop_requested:
        raise Exception("Stopped")
    
    set_status("🎨 Generating texture...", f"Creating {size} texture")
    
    model = "gemini-3-pro-image-preview"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
            "imageConfig": {"aspectRatio": "1:1", "imageSize": size}
        }
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=120) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            
            if 'candidates' in result and result['candidates']:
                parts = result['candidates'][0].get('content', {}).get('parts', [])
                
                for part in parts:
                    if 'inlineData' in part:
                        inline = part['inlineData']
                        img_data = base64.b64decode(inline['data'])
                        ext = '.png' if 'png' in inline.get('mimeType', '') else '.jpg'
                        
                        temp_dir = tempfile.gettempdir()
                        filename = f"forge_texture_{hash(prompt) % 10000:04d}{ext}"
                        filepath = os.path.join(temp_dir, filename)
                        
                        with open(filepath, 'wb') as f:
                            f.write(img_data)
                        
                        _texture_path = filepath
                        set_status("✅ Texture generated", f"Saved: {filename}")
                        log_action(f"[TEXTURE] Generated: {prompt[:40]}...")
                        return filepath, None
                    
                    elif 'text' in part:
                        return None, part['text']
            
            set_status("⚠️ No image", "API returned no image")
            return None, "No image generated"
            
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8') if e.fp else ""
        try:
            msg = json.loads(body).get('error', {}).get('message', '')
        except:
            msg = str(e)
        set_status(f"❌ Texture error", msg[:30])
        raise Exception(msg[:100])


def apply_texture_to_object(obj, image_path):
    mat_name = f"Forge_{obj.name}"
    mat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (300, 0)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    tex_node = nodes.new('ShaderNodeTexImage')
    tex_node.location = (-300, 0)
    tex_node.image = bpy.data.images.load(image_path, check_existing=True)
    
    links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    
    log_action(f"[TEXTURE] Applied to {obj.name}")
    return True


def generate_auto_texture_prompt(obj):
    name = obj.name.lower()
    
    # Get project description for context
    try:
        desc = bpy.context.scene.forge_project_desc
        style = f" in style: {desc}" if desc else ""
    except:
        style = ""
    
    if any(x in name for x in ['wall', 'floor', 'ground']):
        return f"Seamless tileable {name} texture, PBR{style}"
    elif any(x in name for x in ['wood', 'plank']):
        return f"Seamless tileable wood texture, PBR{style}"
    elif any(x in name for x in ['metal', 'steel']):
        return f"Seamless brushed metal texture, PBR{style}"
    elif any(x in name for x in ['stone', 'rock', 'brick']):
        return f"Seamless {name} texture, PBR{style}"
    else:
        return f"Seamless texture for {obj.name}, PBR game-ready{style}"


# =============================================================================
# System Prompt
# =============================================================================

def get_project_context():
    parts = []
    try:
        scene = bpy.context.scene
        desc = scene.forge_project_desc
        if desc:
            parts.append(f"PROJECT: {desc}")
        
        log = get_project_log(scene)
        if log:
            recent = log[-10:]
            parts.append(f"RECENT ACTIONS:\n" + "\n".join(recent))
    except:
        pass
    return "\n\n".join(parts) if parts else ""


def get_system():
    v = ".".join(map(str, bpy.app.version))
    project_ctx = get_project_context()
    project_section = f"\n\nPROJECT CONTEXT\n{project_ctx}" if project_ctx else ""
    
    return f'''You are "BlenderForge AI", expert Blender {v} assistant for UNITY-READY 3D assets.{project_section}

RULES
1) Python code in one ```python block only
2) Max 3 bullet points outside code
3) Meters, Z-up, clean transforms
4) Bone names: .L/.R suffix
5) HUMANOID: hips/spine/chest/neck/head/upperArm.L etc.
6) GENERIC: custom skeleton for non-humanoids
7) IF AMBIGUOUS: Ask "Humanoid or Generic?" - no code
8) Attachment gaps ≤ 0.01m, validate & fix
9) Edit bones in Edit Mode only
10) Build on previous actions from project context'''


# =============================================================================
# Helpers
# =============================================================================

def get_context():
    try:
        obj = bpy.context.active_object
        objs = [o.name for o in bpy.data.objects][:5]
        return f"Active: {obj.name if obj else 'None'}, Objects: {objs}"
    except:
        return ""


def is_question(text):
    patterns = [r'Unity rig type', r'Humanoid.*or.*Generic', r'clarif']
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return text.strip().endswith('?') and len(text) < 400


def extract_code(text):
    if is_question(text):
        return None
    for p in [r'```python\s*\n(.*?)```', r'```\s*\n(.*?)```']:
        m = re.findall(p, text, re.DOTALL)
        if m:
            return m[0].strip()
    return None


def run_code(code):
    set_status(f"⚙️ {model_name()} executing...", "Running code")
    try:
        exec(code, {"bpy": bpy})
        set_status(f"✅ {model_name()} complete", "Code executed")
        log_action("[CODE] Executed successfully")
        return True, "✅ Done"
    except Exception as e:
        set_status(f"❌ Exec error", str(e)[:30])
        log_action(f"[CODE] Error: {str(e)[:40]}")
        return False, f"❌ {e}"


def wrap_text(ctx, text, parent, max_lines=20):
    w = int(ctx.region.width / 7)
    wrapper = textwrap.TextWrapper(width=w)
    n = 0
    for part in text.split("\n"):
        if n >= max_lines:
            parent.label(text="...")
            break
        for line in wrapper.wrap(part) or [""]:
            if n >= max_lines:
                break
            parent.label(text=line)
            n += 1


def test_connection():
    key = get_key()
    if not key:
        set_status("❌ No Key", "")
        return False, "Set API Key"
    
    try:
        model = get_model()
        version = "v1alpha" if "preview" in model else "v1beta"
        url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={key}"
        
        payload = {"contents": [{"role": "user", "parts": [{"text": "Hi"}]}]}
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=10) as resp:
            if 'candidates' in json.loads(resp.read().decode('utf-8')):
                set_status(f"✅ {model_name()} connected", "Ready")
                return True, "OK"
        
        set_status("⚠️ Unexpected", "")
        return False, "Unexpected"
        
    except Exception as e:
        set_status("❌ Failed", str(e)[:30])
        return False, str(e)[:50]


# =============================================================================
# UI - Main Panel
# =============================================================================

class FORGE_PT_main(bpy.types.Panel):
    bl_label = "BlenderForge AI"
    bl_idname = "FORGE_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Forge'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Status bar
        box = layout.box()
        row = box.row(align=True)
        row.label(text=_status)
        row.operator("forge.test", text="", icon='FILE_REFRESH')
        row.operator("forge.prefs", text="", icon='PREFERENCES')
        
        if _last_activity:
            box.label(text=f"→ {_last_activity}", icon='INFO')
        
        if scene.forge_loading:
            row = layout.row()
            row.alert = True
            row.label(text="Working...", icon='TIME')
            row.operator("forge.stop", text="Stop", icon='CANCEL')
        
        layout.separator()
        
        # Project description
        layout.prop(scene, "forge_project_desc", text="", icon='FILE_TEXT')
        
        # Input
        layout.prop(scene, "forge_message", text="")
        
        # Action buttons
        row = layout.row(align=True)
        row.scale_y = 1.4
        row.enabled = not scene.forge_loading
        row.operator("forge.send", text="Send", icon='EXPORT')
        row.operator("forge.clear", text="", icon='TRASH')
        
        # Auto mode toggle
        p = bpy.context.preferences.addons.get(__name__)
        if p:
            layout.prop(p.preferences, "auto_execute", text="🤖 Autonomous")
        
        layout.separator()
        
        # History navigation
        history = get_response_history(scene)
        if history:
            row = layout.row(align=True)
            row.operator("forge.history_prev", text="", icon='TRIA_LEFT')
            row.label(text=f"{_history_index + 1}/{len(history)}")
            row.operator("forge.history_next", text="", icon='TRIA_RIGHT')
        
        # Error
        if scene.forge_error:
            box = layout.box()
            box.alert = True
            box.label(text=scene.forge_error[:60])
        
        # Response
        if scene.forge_response:
            box = layout.box()
            wrap_text(context, scene.forge_response, box)
            
            if scene.forge_code:
                row = layout.row(align=True)
                row.operator("forge.run", text="Run", icon='PLAY')
                row.operator("forge.copy", text="Copy", icon='COPYDOWN')
                
                if scene.forge_result:
                    layout.label(text=scene.forge_result)


# =============================================================================
# UI - Texture Panel
# =============================================================================

class FORGE_PT_texture(bpy.types.Panel):
    bl_label = "🎨 Textures"
    bl_idname = "FORGE_PT_texture"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Forge'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Scene objects
        box = layout.box()
        box.label(text="Objects:", icon='OUTLINER')
        mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH']
        for obj in mesh_objs[:6]:
            has_mat = "🎨" if obj.data.materials else "⬜"
            box.label(text=f"{has_mat} {obj.name}")
        
        layout.separator()
        
        # Texture prompt
        layout.prop(scene, "forge_texture_prompt", text="", icon='TEXTURE')
        
        p = bpy.context.preferences.addons.get(__name__)
        if p:
            layout.prop(p.preferences, "texture_size", text="Size")
        
        # Action buttons
        row = layout.row(align=True)
        row.scale_y = 1.3
        row.enabled = not scene.forge_loading
        row.operator("forge.gen_texture", text="Generate", icon='IMAGE_DATA')
        
        col = layout.column(align=True)
        col.enabled = not scene.forge_loading
        col.operator("forge.auto_texture", text="🤖 Auto Selected", icon='BRUSH_DATA')
        col.operator("forge.auto_texture_all", text="🤖 Auto ALL", icon='RENDERLAYERS')
        
        if scene.forge_texture_result:
            layout.separator()
            layout.label(text=scene.forge_texture_result)
            if _texture_path:
                layout.operator("forge.apply_texture", text="Apply", icon='IMPORT')


# =============================================================================
# UI - Project Panel
# =============================================================================

class FORGE_PT_project(bpy.types.Panel):
    bl_label = "📋 Project Log"
    bl_idname = "FORGE_PT_project"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Forge'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        log = get_project_log(scene)
        if log:
            box = layout.box()
            for entry in log[-10:]:
                box.label(text=entry[:50])
        else:
            layout.label(text="No actions yet")
        
        layout.operator("forge.clear_log", text="Clear Log", icon='TRASH')


# =============================================================================
# Operators
# =============================================================================

class FORGE_OT_test(bpy.types.Operator):
    bl_idname = "forge.test"
    bl_label = "Test"

    def execute(self, context):
        context.scene.forge_loading = True
        def test():
            test_connection()
            def done():
                context.scene.forge_loading = False
                for a in bpy.context.screen.areas:
                    if a.type == 'VIEW_3D': a.tag_redraw()
                return None
            bpy.app.timers.register(done, first_interval=0.1)
        threading.Thread(target=test, daemon=True).start()
        return {'FINISHED'}


class FORGE_OT_prefs(bpy.types.Operator):
    bl_idname = "forge.prefs"
    bl_label = "Prefs"
    def execute(self, context):
        bpy.ops.preferences.addon_show(module=__name__)
        return {'FINISHED'}


class FORGE_OT_stop(bpy.types.Operator):
    bl_idname = "forge.stop"
    bl_label = "Stop"
    def execute(self, context):
        global _stop_requested
        _stop_requested = True
        context.scene.forge_loading = False
        set_status("⏹️ Stopped", "")
        return {'FINISHED'}


class FORGE_OT_send(bpy.types.Operator):
    bl_idname = "forge.send"
    bl_label = "Send"

    def execute(self, context):
        global _stop_requested, _chat_history
        _stop_requested = False
        
        scene = context.scene
        msg = scene.forge_message.strip()
        
        if not msg: return {'CANCELLED'}
        if scene.forge_loading: return {'CANCELLED'}
        if not get_key():
            bpy.ops.forge.prefs()
            return {'CANCELLED'}
        
        scene.forge_error = ""
        scene.forge_loading = True
        scene.forge_code = ""
        scene.forge_result = ""
        
        log_action(f"[USER] {msg[:50]}...")
        
        full_msg = f"[Scene: {get_context()}]\n\n{msg}"
        _chat_history.append({"role": "user", "parts": [{"text": full_msg}]})
        
        def send():
            try:
                resp = call_api(_chat_history, get_system())
                _chat_history.append({"role": "model", "parts": [{"text": resp}]})
                code = extract_code(resp)
                
                def done():
                    if _stop_requested:
                        scene.forge_loading = False
                        return None
                    
                    scene.forge_response = resp
                    scene.forge_code = code or ""
                    scene.forge_message = ""
                    
                    add_to_history(scene, resp, code or "")
                    
                    if is_auto() and code:
                        run_code(code)
                        scene.forge_result = "✅ Auto-executed"
                    
                    scene.forge_loading = False
                    for a in bpy.context.screen.areas:
                        if a.type == 'VIEW_3D': a.tag_redraw()
                    return None
                
                bpy.app.timers.register(done, first_interval=0.1)
                
            except Exception as e:
                if _chat_history and _chat_history[-1]["role"] == "user":
                    _chat_history.pop()
                def err():
                    scene.forge_error = str(e)[:80]
                    scene.forge_loading = False
                    return None
                bpy.app.timers.register(err, first_interval=0.1)
        
        threading.Thread(target=send, daemon=True).start()
        return {'FINISHED'}


class FORGE_OT_run(bpy.types.Operator):
    bl_idname = "forge.run"
    bl_label = "Run"
    def execute(self, context):
        if context.scene.forge_code:
            ok, msg = run_code(context.scene.forge_code)
            context.scene.forge_result = msg
        return {'FINISHED'}


class FORGE_OT_copy(bpy.types.Operator):
    bl_idname = "forge.copy"
    bl_label = "Copy"
    def execute(self, context):
        if context.scene.forge_code:
            context.window_manager.clipboard = context.scene.forge_code
        return {'FINISHED'}


class FORGE_OT_clear(bpy.types.Operator):
    bl_idname = "forge.clear"
    bl_label = "Clear"
    def execute(self, context):
        global _chat_history, _history_index
        _chat_history = []
        _history_index = -1
        s = context.scene
        s.forge_message = ""
        s.forge_response = ""
        s.forge_error = ""
        s.forge_code = ""
        s.forge_result = ""
        set_status("⚪ Ready", "Cleared")
        return {'FINISHED'}


class FORGE_OT_clear_log(bpy.types.Operator):
    bl_idname = "forge.clear_log"
    bl_label = "Clear Log"
    def execute(self, context):
        set_project_log(context.scene, [])
        context.scene.forge_response_history = ""
        return {'FINISHED'}


class FORGE_OT_history_prev(bpy.types.Operator):
    bl_idname = "forge.history_prev"
    bl_label = "Previous"
    def execute(self, context):
        global _history_index
        history = get_response_history(context.scene)
        if history and _history_index > 0:
            _history_index -= 1
            entry = history[_history_index]
            context.scene.forge_response = entry["response"]
            context.scene.forge_code = entry["code"]
        return {'FINISHED'}


class FORGE_OT_history_next(bpy.types.Operator):
    bl_idname = "forge.history_next"
    bl_label = "Next"
    def execute(self, context):
        global _history_index
        history = get_response_history(context.scene)
        if history and _history_index < len(history) - 1:
            _history_index += 1
            entry = history[_history_index]
            context.scene.forge_response = entry["response"]
            context.scene.forge_code = entry["code"]
        return {'FINISHED'}


# Texture operators
class FORGE_OT_gen_texture(bpy.types.Operator):
    bl_idname = "forge.gen_texture"
    bl_label = "Generate"
    def execute(self, context):
        global _stop_requested
        _stop_requested = False
        scene = context.scene
        prompt = scene.forge_texture_prompt.strip()
        if not prompt: return {'CANCELLED'}
        if not get_key():
            bpy.ops.forge.prefs()
            return {'CANCELLED'}
        
        scene.forge_loading = True
        scene.forge_texture_result = ""
        size = get_texture_size()
        
        def gen():
            try:
                path, _ = generate_texture(prompt, size)
                def done():
                    scene.forge_loading = False
                    scene.forge_texture_result = f"✅ {os.path.basename(path)}" if path else "No image"
                    for a in bpy.context.screen.areas:
                        if a.type == 'VIEW_3D': a.tag_redraw()
                    return None
                bpy.app.timers.register(done, first_interval=0.1)
            except Exception as e:
                def err():
                    scene.forge_loading = False
                    scene.forge_texture_result = f"❌ {str(e)[:60]}"
                    return None
                bpy.app.timers.register(err, first_interval=0.1)
        
        threading.Thread(target=gen, daemon=True).start()
        return {'FINISHED'}


class FORGE_OT_apply_texture(bpy.types.Operator):
    bl_idname = "forge.apply_texture"
    bl_label = "Apply"
    def execute(self, context):
        if not _texture_path or not os.path.exists(_texture_path): return {'CANCELLED'}
        obj = context.active_object
        if not obj or obj.type != 'MESH': return {'CANCELLED'}
        apply_texture_to_object(obj, _texture_path)
        return {'FINISHED'}


class FORGE_OT_auto_texture(bpy.types.Operator):
    bl_idname = "forge.auto_texture"
    bl_label = "Auto"
    def execute(self, context):
        global _stop_requested
        _stop_requested = False
        obj = context.active_object
        if not obj or obj.type != 'MESH': return {'CANCELLED'}
        if not get_key():
            bpy.ops.forge.prefs()
            return {'CANCELLED'}
        
        scene = context.scene
        scene.forge_loading = True
        prompt = generate_auto_texture_prompt(obj)
        size = get_texture_size()
        
        def gen():
            try:
                path, _ = generate_texture(prompt, size)
                def done():
                    if path: apply_texture_to_object(obj, path)
                    scene.forge_loading = False
                    scene.forge_texture_result = f"✅ {obj.name}" if path else "Failed"
                    for a in bpy.context.screen.areas:
                        if a.type == 'VIEW_3D': a.tag_redraw()
                    return None
                bpy.app.timers.register(done, first_interval=0.1)
            except Exception as e:
                def err():
                    scene.forge_loading = False
                    scene.forge_texture_result = f"❌ {str(e)[:60]}"
                    return None
                bpy.app.timers.register(err, first_interval=0.1)
        
        threading.Thread(target=gen, daemon=True).start()
        return {'FINISHED'}


class FORGE_OT_auto_texture_all(bpy.types.Operator):
    bl_idname = "forge.auto_texture_all"
    bl_label = "Auto All"
    def execute(self, context):
        global _stop_requested
        _stop_requested = False
        mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH']
        if not mesh_objs: return {'CANCELLED'}
        if not get_key():
            bpy.ops.forge.prefs()
            return {'CANCELLED'}
        
        scene = context.scene
        scene.forge_loading = True
        size = get_texture_size()
        
        def gen_all():
            done_count = [0]
            for i, obj in enumerate(mesh_objs):
                if _stop_requested: break
                set_status(f"🎨 {i+1}/{len(mesh_objs)}", obj.name)
                try:
                    prompt = generate_auto_texture_prompt(obj)
                    path, _ = generate_texture(prompt, size)
                    if path:
                        def apply_tex(o=obj, p=path):
                            apply_texture_to_object(o, p)
                            return None
                        bpy.app.timers.register(apply_tex, first_interval=0.1)
                        done_count[0] += 1
                except: pass
            
            def finish():
                scene.forge_loading = False
                scene.forge_texture_result = f"✅ {done_count[0]}/{len(mesh_objs)}"
                set_status("✅ Done", "")
                for a in bpy.context.screen.areas:
                    if a.type == 'VIEW_3D': a.tag_redraw()
                return None
            bpy.app.timers.register(finish, first_interval=0.5)
        
        threading.Thread(target=gen_all, daemon=True).start()
        return {'FINISHED'}


# =============================================================================
# Registration
# =============================================================================

classes = (
    ForgePreferences,
    FORGE_PT_main,
    FORGE_PT_texture,
    FORGE_PT_project,
    FORGE_OT_test,
    FORGE_OT_prefs,
    FORGE_OT_stop,
    FORGE_OT_send,
    FORGE_OT_run,
    FORGE_OT_copy,
    FORGE_OT_clear,
    FORGE_OT_clear_log,
    FORGE_OT_history_prev,
    FORGE_OT_history_next,
    FORGE_OT_gen_texture,
    FORGE_OT_apply_texture,
    FORGE_OT_auto_texture,
    FORGE_OT_auto_texture_all,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.forge_message = bpy.props.StringProperty(name="Message")
    bpy.types.Scene.forge_response = bpy.props.StringProperty(name="Response")
    bpy.types.Scene.forge_error = bpy.props.StringProperty(name="Error")
    bpy.types.Scene.forge_code = bpy.props.StringProperty(name="Code")
    bpy.types.Scene.forge_result = bpy.props.StringProperty(name="Result")
    bpy.types.Scene.forge_loading = bpy.props.BoolProperty(name="Loading")
    bpy.types.Scene.forge_texture_prompt = bpy.props.StringProperty(name="Texture")
    bpy.types.Scene.forge_texture_result = bpy.props.StringProperty(name="Tex Result")
    bpy.types.Scene.forge_project_desc = bpy.props.StringProperty(
        name="Project",
        description="Project description - shared context for AI"
    )
    bpy.types.Scene.forge_project_log = bpy.props.StringProperty(
        name="Log",
        description="Project action log (JSON)"
    )
    bpy.types.Scene.forge_response_history = bpy.props.StringProperty(
        name="History",
        description="Response history (JSON)"
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    for p in ['forge_message', 'forge_response', 'forge_error', 'forge_code',
              'forge_result', 'forge_loading', 'forge_texture_prompt', 'forge_texture_result',
              'forge_project_desc', 'forge_project_log', 'forge_response_history']:
        if hasattr(bpy.types.Scene, p):
            delattr(bpy.types.Scene, p)


if __name__ == "__main__":
    register()
