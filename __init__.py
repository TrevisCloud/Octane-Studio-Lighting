bl_info = {
    "name": "Octane Studio Lighting",
    "author": "TrevisCloud",
    "version": (1, 0, 0),
    "blender": (4, 5, 2),
    "location": "View3D > N-Panel > Octane Studio",
    "description": "Professional Studio Lighting and Camera Tools for OctaneRender. Features: 3 Lighting Styles, Per-Light Control, Kelvin/RGB, Presets, Studio Backdrop, Advanced Camera Controls.",
    "category": "Lighting",
}

import bpy
import math
from mathutils import Vector

# ------------------------------------------------------------------------
#   CONSTANTS
# ------------------------------------------------------------------------

COLLECTION_NAME = "Octane_Studio_Setup"

OFFSETS = {
    'LOW_KEY': {
        'KEY': Vector((-2, -2, 2)),
        'FILL': Vector((2, -3, 1)),
        'RIM': Vector((1, 2, 2))
    },
    'BUTTERFLY': {
        'KEY': Vector((0, -2, 2.5)),
        'FILL': Vector((0, -2, 0.5)),
        'RIM': Vector((-1.5, 1.5, 1.5))
    },
    'SPLIT': {
        'KEY': Vector((-2.5, 0, 0)),
        'FILL': Vector((2.5, -1, 1)),
        'RIM': Vector((0, 2, 2))
    }
}

# ------------------------------------------------------------------------
#   UTILITIES
# ------------------------------------------------------------------------

def get_lighting_target(context):
    """Returns the main lighting target object (from UI picker or fallback)."""
    props = context.scene.octane_studio_props
    
    # 1. Explicit Lighting Picker
    if props.target_object:
        return props.target_object

    # 2. Existing internal Studio Null
    if "Studio_Target_Null" in bpy.data.objects:
        return bpy.data.objects["Studio_Target_Null"]
    
    # 3. Fallback: Create a new Studio Null if no active object or an unsuitable one is selected
    obj = context.active_object
    if not obj or "Studio_" in obj.name or obj.type == 'LIGHT' or obj.type == 'CAMERA':
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0,0,1.6))
        obj = context.active_object
        obj.name = "Studio_Target_Null"
        # Link to our collection for cleanup
        col = get_or_create_collection()
        if obj.users_collection:
             for c in obj.users_collection: c.objects.unlink(obj)
        col.objects.link(obj)
    return obj

def get_camera_focus_target(context):
    """Returns the specific target for the camera (or falls back to main lighting target)."""
    props = context.scene.octane_studio_props
    if props.camera_target:
        return props.camera_target
    return get_lighting_target(context) # Fallback to main lighting target

def get_or_create_collection():
    """Gets our dedicated collection, creating it if it doesn't exist."""
    col = bpy.data.collections.get(COLLECTION_NAME)
    if not col:
        col = bpy.data.collections.new(COLLECTION_NAME)
        bpy.context.scene.collection.children.link(col)
    return col

def find_light_object(role):
    """Finds a specific light object (e.g., Key, Fill, Rim) in our collection."""
    col = bpy.data.collections.get(COLLECTION_NAME)
    if not col: return None
    for obj in col.objects:
        if obj.get("studio_role") == role:
            return obj
    return None

def get_portrait_cam():
    """Returns the 'Portrait_Cam' object if it exists."""
    return bpy.data.objects.get("Portrait_Cam")

# ------------------------------------------------------------------------
#   LIVE UPDATES: LIGHTS
# ------------------------------------------------------------------------

def update_light_node(context, role, settings):
    """Updates Octane nodes, Visibility, Size, and Position for a specific light role."""
    obj = find_light_object(role)
    if not obj: return

    # 1. Update Visibility (On/Off)
    is_hidden = not settings.enabled
    obj.hide_viewport = is_hidden
    obj.hide_render = is_hidden

    # 2. Update Size (Softness) - Applicable to Area Lights
    if obj.type == 'LIGHT':
        if obj.data.type == 'AREA':
            obj.data.size = settings.size
            obj.data.size_y = settings.size # Keep square for area lights
        elif obj.data.type == 'SPOT':
            # Spot lights use 'shadow_soft_size' for softness
            obj.data.shadow_soft_size = settings.size # This property exists for Eevee/Cycles spots too

    # 3. Update Position/Distance relative to the main lighting target
    target = get_lighting_target(context)
    if target and "studio_style" in obj:
        style = obj["studio_style"]
        if style in OFFSETS and role in OFFSETS[style]:
            base_vec = OFFSETS[style][role]
            obj.location = target.location + (base_vec * settings.distance)

    if not obj.data.use_nodes: return # Only proceed if Octane nodes are enabled

    # 4. Update Octane Nodes
    nt = obj.data.node_tree
    tex_emit = None
    for node in nt.nodes:
        if node.bl_idname == 'OctaneTextureEmission':
            tex_emit = node
            break
            
    if tex_emit:
        # A. Update Power
        if 'Power' in tex_emit.inputs:
            tex_emit.inputs['Power'].default_value = settings.power
        elif len(tex_emit.inputs) > 1: # Fallback to index if 'Power' name isn't found
            tex_emit.inputs[1].default_value = settings.power

        # B. Update Color/Temperature (via the connected source node)
        if len(tex_emit.inputs) > 0 and tex_emit.inputs[0].is_linked:
            source_node = tex_emit.inputs[0].links[0].from_node
            
            # Update OctaneRGBColor node
            if source_node.bl_idname == 'OctaneRGBColor':
                rgba = (settings.color[0], settings.color[1], settings.color[2], 1)
                # Prioritize 'Value' or 'Color' by name, then fallback to index 0
                if 'Value' in source_node.inputs:
                     source_node.inputs['Value'].default_value = rgba
                elif 'Color' in source_node.inputs:
                     source_node.inputs['Color'].default_value = rgba
                elif len(source_node.inputs) > 0:
                    source_node.inputs[0].default_value = rgba

            # Update OctaneBlackBody node
            elif source_node.bl_idname == 'OctaneBlackBody':
                # Prioritize 'Temperature' by name, then fallback to index 0
                if 'Temperature' in source_node.inputs:
                    source_node.inputs['Temperature'].default_value = settings.kelvin
                elif len(source_node.inputs) > 0:
                    source_node.inputs[0].default_value = settings.kelvin

def update_all_lights(self, context):
    """Callback for UI updates - ensures all lights react to property changes."""
    props = context.scene.octane_studio_props
    update_light_node(context, 'KEY', props.key_light)
    update_light_node(context, 'FILL', props.fill_light)
    update_light_node(context, 'RIM', props.rim_light)

# ------------------------------------------------------------------------
#   LIVE UPDATES: CAMERA
# ------------------------------------------------------------------------

def update_camera_transform(self, context):
    """Calculates camera position based on orbit properties relative to Camera Focus Target."""
    cam = get_portrait_cam()
    props = context.scene.octane_studio_props
    
    if not cam or not props.camera_locked: return
    
    # Use the specific camera focus target
    target = get_camera_focus_target(context)
    if not target: return
    
    # Orbit Math
    dist = props.camera_dist
    angle = props.camera_orbit
    height = props.camera_height
    
    # Calculate X,Y on circle around the target
    # math.pi is added to 'angle' to make 0 degrees point directly in front (Blender's -Y direction)
    x = target.location.x + (dist * math.sin(angle))
    y = target.location.y - (dist * math.cos(angle))
    z = target.location.z + height
    
    cam.location = (x, y, z)
    
    # Ensure constraint is also pointing at the right thing
    update_camera_lock(self, context)

def update_camera_lock(self, context):
    """Enables/Disables/Updates the Track To constraint on the camera."""
    cam = get_portrait_cam()
    if not cam: return
    
    props = context.scene.octane_studio_props
    
    # Find existing Track To constraint
    const = None
    for c in cam.constraints:
        if c.type == 'TRACK_TO':
            const = c
            break
            
    if props.camera_locked:
        # If locked, ensure constraint exists and is enabled
        if not const:
            const = cam.constraints.new('TRACK_TO')
        
        # Point to the specific camera focus target
        target = get_camera_focus_target(context)
        
        const.target = target
        const.track_axis = 'TRACK_NEGATIVE_Z' # Camera typically points down its -Z axis
        const.up_axis = 'UP_Y' # Maintain upright orientation
        const.mute = False # Enable constraint
        
        # Immediately snap camera to the calculated orbital position
        update_camera_transform(self, context)
        
    else:
        # If unlocked, mute the constraint to allow free movement
        if const:
            const.mute = True

# ------------------------------------------------------------------------
#   SYNC LOGIC (Reverse: Scene -> UI for "Sync UI" operator)
# ------------------------------------------------------------------------

def sync_settings_from_obj(obj, settings):
    """Reads values from a scene object's data/nodes and updates UI properties."""
    if not obj: return
    
    # Sync Visibility
    settings.enabled = not obj.hide_render # Assuming hide_render is the primary toggle
    
    # Sync Size (for Area Lights)
    if obj.data.type == 'AREA':
        settings.size = obj.data.size
    
    # Sync Node-based properties
    if not obj.data.use_nodes: return
    nt = obj.data.node_tree
    
    tex_emit = None
    for node in nt.nodes:
        if node.bl_idname == 'OctaneTextureEmission':
            tex_emit = node
            break
    
    if tex_emit:
        # Sync Power
        if 'Power' in tex_emit.inputs:
            settings.power = tex_emit.inputs['Power'].default_value
        elif len(tex_emit.inputs) > 1: # Fallback
            settings.power = tex_emit.inputs[1].default_value
            
        # Sync Color/Kelvin by inspecting the connected node
        if len(tex_emit.inputs) > 0 and tex_emit.inputs[0].is_linked:
            src = tex_emit.inputs[0].links[0].from_node
            
            if src.bl_idname == 'OctaneRGBColor':
                settings.use_kelvin = False
                val = (1,1,1,1)
                # Read from 'Value' or 'Color' name, fallback to index 0
                if 'Value' in src.inputs: val = src.inputs['Value'].default_value
                elif 'Color' in src.inputs: val = src.inputs['Color'].default_value
                elif len(src.inputs) > 0: val = src.inputs[0].default_value
                
                if hasattr(val, '__len__') and len(val) >= 3:
                     settings.color = (val[0], val[1], val[2])
                
            elif src.bl_idname == 'OctaneBlackBody':
                settings.use_kelvin = True
                val = 6500
                # Read from 'Temperature' name, fallback to index 0
                if 'Temperature' in src.inputs: val = src.inputs['Temperature'].default_value
                elif len(src.inputs) > 0: val = src.inputs[0].default_value
                settings.kelvin = val

# ------------------------------------------------------------------------
#   DATA CLASSES (Property Groups)
# ------------------------------------------------------------------------

class LightSettings(bpy.types.PropertyGroup):
    """Settings for a single light (Key, Fill, or Rim)."""
    
    enabled: bpy.props.BoolProperty(
        name="Enable", default=True, update=update_all_lights,
        description="Toggle this light On/Off in Viewport and Render."
    )
    expanded: bpy.props.BoolProperty(
        name="Expanded", default=True,
        description="Expand or collapse the settings panel for this light."
    )
    use_kelvin: bpy.props.BoolProperty(
        name="Use Kelvin", default=False, update=update_all_lights,
        description="Switch between Kelvin Temperature and RGB color control. (Requires 'Create Setup' to apply node change)."
    )
    power: bpy.props.FloatProperty(
        name="Power", default=15.0, min=0.0, soft_max=500.0, update=update_all_lights,
        description="Intensity of the light."
    )
    color: bpy.props.FloatVectorProperty(
        name="RGB", subtype='COLOR', default=(1,1,1), min=0.0, max=1.0, update=update_all_lights,
        description="RGB color value for the light (if not using Kelvin)."
    )
    kelvin: bpy.props.FloatProperty(
        name="Temp (K)", default=6500, min=1000, max=12000, update=update_all_lights,
        description="Color temperature in Kelvin (1000K=warm, 12000K=cool, if using Kelvin)."
    )
    distance: bpy.props.FloatProperty(
        name="Distance", default=1.0, min=0.1, max=10.0, update=update_all_lights,
        description="Distance multiplier from the target object. Adjusts light position."
    )
    size: bpy.props.FloatProperty(
        name="Size", default=1.0, min=0.1, max=10.0, update=update_all_lights,
        description="Physical size of the light. Larger size results in softer shadows."
    )

class OctaneStudioProperties(bpy.types.PropertyGroup):
    """Main property group for the Octane Studio add-on."""
    
    # UI Tab Switcher
    ui_tab: bpy.props.EnumProperty(
        items=[('CREATE', "Create", "Setup your scene and initial lighting."), 
               ('CONTROL', "Control", "Adjust individual light settings in real-time."), 
               ('TOOLS', "Tools", "Access camera, presets, and environment helpers.")],
        default='CREATE',
        description="Switch between different sections of the add-on."
    )

    # Creation Tab Properties
    setup_type: bpy.props.EnumProperty(
        name="Style",
        items=[('LOW_KEY', "Low Key", "Dramatic, high-contrast lighting, often with strong shadows."),
               ('BUTTERFLY', "Butterfly", "A classic beauty lighting with a butterfly-shaped shadow under the nose."),
               ('SPLIT', "Side/Split", "Divides the face into light and shadow halves for a dramatic effect.")],
        default='LOW_KEY',
        description="Select the desired portrait lighting style to generate."
    )
    
    target_object: bpy.props.PointerProperty(
        type=bpy.types.Object, name="Light Target", 
        description="The object or Empty that all lights will point towards and orbit. Leave empty to auto-create 'Studio_Target_Null'."
    )
    
    # Global toggles for creation
    use_fill: bpy.props.BoolProperty(name="Fill Light", default=True, description="Include a fill light in the setup to soften shadows.")
    use_rim: bpy.props.BoolProperty(name="Rim Light", default=True, description="Include a rim/kicker light to separate the subject from the background.")
    
    # Pointers to individual light settings
    key_light: bpy.props.PointerProperty(type=LightSettings)
    fill_light: bpy.props.PointerProperty(type=LightSettings)
    rim_light: bpy.props.PointerProperty(type=LightSettings)

    # Saved Presets (hidden properties for internal storage)
    saved_key: bpy.props.PointerProperty(type=LightSettings)
    saved_fill: bpy.props.PointerProperty(type=LightSettings)
    saved_rim: bpy.props.PointerProperty(type=LightSettings)
    
    # CAMERA CONTROLS Properties
    camera_target: bpy.props.PointerProperty(
        type=bpy.types.Object, name="Focus Target",
        description="The specific object the camera will look at and orbit. If empty, the main 'Light Target' is used.",
        update=update_camera_transform # Update camera position/constraint if target changes
    )
    camera_locked: bpy.props.BoolProperty(
        name="Lock to Target", default=True, update=update_camera_lock,
        description="When enabled, the camera is constrained to look at the 'Focus Target' and orbits it via sliders. Disable to move camera freely."
    )
    camera_dist: bpy.props.FloatProperty(
        name="Cam Distance", default=5.0, min=0.5, max=20.0,
        description="Distance of the camera from its focus target.",
        update=update_camera_transform
    )
    camera_height: bpy.props.FloatProperty(
        name="Cam Height", default=0.0, min=-5.0, max=5.0,
        description="Vertical height of the camera relative to the focus target's Z-axis.",
        update=update_camera_transform
    )
    camera_orbit: bpy.props.FloatProperty(
        name="Orbit Angle", default=0.0, min=-math.pi, max=math.pi, subtype='ANGLE',
        description="Rotation angle around the focus target (0=front, pi/2=right, pi=back).",
        update=update_camera_transform
    )

# ------------------------------------------------------------------------
#   OPERATORS
# ------------------------------------------------------------------------

class OCTANESTUDIO_OT_Generate(bpy.types.Operator):
    """Generates the selected studio lighting setup based on current UI settings."""
    bl_idname = "octanestudio.generate"
    bl_label = "Create Setup"
    
    def execute(self, context):
        create_full_setup(context)
        context.scene.octane_studio_props.ui_tab = 'CONTROL' # Switch to Control tab after creation
        self.report({'INFO'}, f"Created {context.scene.octane_studio_props.setup_type} Setup.")
        return {'FINISHED'}

class OCTANESTUDIO_OT_Clear(bpy.types.Operator):
    """Removes all objects created by the Octane Studio add-on (lights, target, backdrop, camera)."""
    bl_idname = "octanestudio.clear"
    bl_label = "Clear Lights" # Short label for UI
    
    def execute(self, context):
        col = get_or_create_collection()
        # Create a list to avoid modifying during iteration
        for obj in list(col.objects): 
            bpy.data.objects.remove(obj, do_unlink=True)
        
        # Remove the main target null if it's ours and no other object is using it
        if "Studio_Target_Null" in bpy.data.objects:
            target_null = bpy.data.objects["Studio_Target_Null"]
            if target_null.users == 1: # Only linked to collection
                bpy.data.objects.remove(target_null, do_unlink=True)

        # Remove the camera if it's ours
        cam_obj = get_portrait_cam()
        if cam_obj and cam_obj.users == 1:
             bpy.data.objects.remove(cam_obj, do_unlink=True)

        bpy.data.collections.remove(col) # Remove the collection itself
        self.report({'INFO'}, "Octane Studio objects cleared.")
        return {'FINISHED'}

class OCTANESTUDIO_OT_AddCamera(bpy.types.Operator):
    """Adds a 'Portrait_Cam' (85mm focal length) and sets it up to track the target."""
    bl_idname = "octanestudio.add_camera"
    bl_label = "Add Portrait Cam"
    
    def execute(self, context):
        props = context.scene.octane_studio_props
        
        # Check if camera already exists
        cam_obj = get_portrait_cam()
        if not cam_obj:
            cam_data = bpy.data.cameras.new("Portrait_Cam")
            cam_data.lens = 85 # Standard portrait focal length
            cam_obj = bpy.data.objects.new("Portrait_Cam", cam_data)
            col = get_or_create_collection()
            col.objects.link(cam_obj)
        
        # Initialize camera properties in the UI
        props.camera_locked = True
        props.camera_dist = 5.0
        props.camera_height = 0.0
        props.camera_orbit = 0.0
        
        # Apply the logic to position and constrain the camera
        update_camera_lock(self, context)
        update_camera_transform(self, context)
        
        # Set this camera as the active scene camera
        context.scene.camera = cam_obj
        
        self.report({'INFO'}, "Portrait Camera added and set active.")
        return {'FINISHED'}

class OCTANESTUDIO_OT_StudioBlack(bpy.types.Operator):
    """Sets the World Background to pure black and disables its strength."""
    bl_idname = "octanestudio.studio_black"
    bl_label = "Set Studio Black"
    
    def execute(self, context):
        world = context.scene.world
        if not world: # Create a world if none exists
            world = bpy.data.worlds.new("StudioWorld")
            context.scene.world = world
            
        world.use_nodes = True
        bg = world.node_tree.nodes.get('Background')
        if not bg: # Create Background node if it doesn't exist
            bg = world.node_tree.nodes.new('ShaderNodeBackground')
            bg.location = (0,0)
            world_output = world.node_tree.nodes.get('World Output')
            if world_output:
                world.node_tree.links.new(bg.outputs['Background'], world_output.inputs['Surface'])
            
        bg.inputs['Color'].default_value = (0, 0, 0, 1) # Pure Black
        bg.inputs['Strength'].default_value = 0 # No strength from world background
            
        self.report({'INFO'}, "World environment set to Black.")
        return {'FINISHED'}

class OCTANESTUDIO_OT_SyncUI(bpy.types.Operator):
    """Reads current settings from the scene's generated lights and updates the UI sliders."""
    bl_idname = "octanestudio.sync_ui"
    bl_label = "Sync UI from Scene"
    
    def execute(self, context):
        props = context.scene.octane_studio_props
        
        k = find_light_object('KEY')
        f = find_light_object('FILL')
        r = find_light_object('RIM')
        
        if k: sync_settings_from_obj(k, props.key_light)
        if f: sync_settings_from_obj(f, props.fill_light)
        if r: sync_settings_from_obj(r, props.rim_light)
        
        self.report({'INFO'}, "UI sliders synced from scene objects.")
        return {'FINISHED'}

class OCTANESTUDIO_OT_SavePreset(bpy.types.Operator):
    """Saves the current light settings (power, color, distance, size, enabled, kelvin mode) to an internal preset."""
    bl_idname = "octanestudio.save_preset"
    bl_label = "Save Preset"
    
    def copy_settings(self, source, dest):
        """Helper to copy properties from one LightSettings group to another."""
        dest.enabled = source.enabled
        dest.power = source.power
        dest.distance = source.distance
        dest.size = source.size
        dest.color = source.color
        dest.use_kelvin = source.use_kelvin
        dest.kelvin = source.kelvin

    def execute(self, context):
        p = context.scene.octane_studio_props
        self.copy_settings(p.key_light, p.saved_key)
        self.copy_settings(p.fill_light, p.saved_fill)
        self.copy_settings(p.rim_light, p.saved_rim)
        self.report({'INFO'}, "Current light settings saved as a preset.")
        return {'FINISHED'}

class OCTANESTUDIO_OT_LoadPreset(bpy.types.Operator):
    """Loads previously saved light settings into the UI and updates the scene lights."""
    bl_idname = "octanestudio.load_preset"
    bl_label = "Load Preset"
    
    def copy_settings(self, source, dest):
        """Helper to copy properties from one LightSettings group to another."""
        dest.enabled = source.enabled
        dest.power = source.power
        dest.distance = source.distance
        dest.size = source.size
        dest.color = source.color
        dest.use_kelvin = source.use_kelvin
        dest.kelvin = source.kelvin

    def execute(self, context):
        p = context.scene.octane_studio_props
        self.copy_settings(p.saved_key, p.key_light)
        self.copy_settings(p.saved_fill, p.fill_light)
        self.copy_settings(p.saved_rim, p.rim_light)
        update_all_lights(self, context) # Ensure scene lights reflect the loaded values
        self.report({'INFO'}, "Preset loaded and applied to lights.")
        return {'FINISHED'}

class OCTANESTUDIO_OT_ResetValues(bpy.types.Operator):
    """Resets all light control sliders to their default factory values."""
    bl_idname = "octanestudio.reset_values"
    bl_label = "Reset Values"
    
    def reset_light_settings_to_defaults(self, settings):
        """Helper to reset a single LightSettings property group."""
        settings.enabled = True
        settings.power = 15.0 # Default power
        settings.distance = 1.0 # Default distance multiplier
        settings.size = 1.0 # Default size
        settings.color = (1.0, 1.0, 1.0) # Default white
        settings.kelvin = 6500 # Default daylight temp
        settings.use_kelvin = False # Default to RGB
        settings.expanded = True # Keep panels expanded on reset for visibility

    def execute(self, context):
        p = context.scene.octane_studio_props
        self.reset_light_settings_to_defaults(p.key_light)
        self.reset_light_settings_to_defaults(p.fill_light)
        self.reset_light_settings_to_defaults(p.rim_light)
        update_all_lights(self, context) # Apply reset values to scene lights
        self.report({'INFO'}, "All light control values reset to defaults.")
        return {'FINISHED'}

class OCTANESTUDIO_OT_AddBackdrop(bpy.types.Operator):
    """Adds a simple curved studio backdrop (plane rotated as a wall)."""
    bl_idname = "octanestudio.add_backdrop"
    bl_label = "Add Backdrop"
    
    def execute(self, context):
        col = get_or_create_collection()
        target = get_lighting_target(context)
        
        # Check if a backdrop already exists to avoid duplicates
        for obj in col.objects:
            if obj.name.startswith("Backdrop"):
                self.report({'INFO'}, "Backdrop already exists. Remove manually or use 'Clear Lights'.")
                return {'FINISHED'}
        
        # Create a plane and position it behind the target
        bpy.ops.mesh.primitive_plane_add(size=10, location=(target.location.x, target.location.y+3, 0))
        bd = context.active_object
        bd.name = "Backdrop"
        bd.rotation_euler = (math.radians(90), 0, 0) # Rotate to stand upright
        
        # Unlink from default collection and link to ours
        if bd.users_collection:
            for c in bd.users_collection: c.objects.unlink(bd)
        col.objects.link(bd)
        
        self.report({'INFO'}, "Studio backdrop added.")
        return {'FINISHED'}

# ------------------------------------------------------------------------
#   CREATION LOGIC
# ------------------------------------------------------------------------

def create_full_setup(context):
    """Creates/rebuilds the entire lighting setup based on selected style and UI properties."""
    props = context.scene.octane_studio_props
    
    # 1. Clear any existing studio objects before creating new ones
    col = get_or_create_collection()
    for obj in list(col.objects): # Iterate over a copy of the list
        bpy.data.objects.remove(obj, do_unlink=True)
    
    # Also clean up the main target null if it's ours and not linked elsewhere
    if "Studio_Target_Null" in bpy.data.objects:
        target_null = bpy.data.objects["Studio_Target_Null"]
        if target_null.users == 1: # Only linked to collection
            bpy.data.objects.remove(target_null, do_unlink=True)

    # Re-acquire target as it might have been deleted/recreated
    target = get_lighting_target(context) 
    style = props.setup_type
    
    def build_light(role, settings_group):
        """Helper function to create an individual Octane-ready light."""
        if role not in OFFSETS[style]: return # Don't build if role isn't part of this style
        
        # Calculate light position
        base_vec = OFFSETS[style][role]
        loc = target.location + (base_vec * settings_group.distance)
        
        # Create Blender Light Data Block
        lname = f"{role}_{style}"
        ldata = bpy.data.lights.new(name=lname, type='AREA') # Currently only Area lights are implemented for these roles
        ldata.shape = 'RECTANGLE'
        ldata.size = settings_group.size
        ldata.use_nodes = True # Crucial for Octane node setup
        
        # ---------------------------------------------------------
        # Octane Node Setup: [Color/Blackbody] -> [TextureEmission] -> [DiffuseMaterial] -> [LightOutput]
        # ---------------------------------------------------------
        nt = ldata.node_tree
        nt.nodes.clear() # Clear any default nodes
        
        # Nodes in order of creation/connection
        out_node = nt.nodes.new('ShaderNodeOutputLight') # Standard Blender Light Output
        out_node.location = (600,0)
        
        diff_mat = nt.nodes.new('OctaneDiffuseMaterial') # Octane's core material for emission
        diff_mat.location = (400,0)
        
        tex_emit = nt.nodes.new('OctaneTextureEmission') # Octane's emission node
        tex_emit.location = (200,0)
        
        # Determine Color Source node (RGB or Blackbody)
        if settings_group.use_kelvin:
            col_node = nt.nodes.new('OctaneBlackBody') # Octane Blackbody node
            col_node.location = (0,0)
            if len(col_node.inputs) > 0: col_node.inputs[0].default_value = settings_group.kelvin
            if 'Normalize' in col_node.inputs: col_node.inputs['Normalize'].default_value = True # Often useful for Blackbody
        else:
            col_node = nt.nodes.new('OctaneRGBColor') # Octane RGB Color node
            col_node.location = (0,0)
            rgba = (settings_group.color[0], settings_group.color[1], settings_group.color[2], 1)
            if len(col_node.inputs) > 0: col_node.inputs[0].default_value = rgba
            
        # Wire up the nodes
        # Color Source (output 0) -> Texture Emission (input 'Texture' / index 0)
        if len(tex_emit.inputs) > 0: nt.links.new(col_node.outputs[0], tex_emit.inputs[0])
            
        # Texture Emission (output 0) -> Diffuse Material (input 'Emission' / index 17)
        emission_socket = None
        if 'Emission' in diff_mat.inputs: emit_socket = diff_mat.inputs['Emission']
        else: 
            for s in mat.inputs: -=
                if s.identifier == 'Emission': emit_socket = s; break
        if emit_socket:
            nt.links.new(tex_emit.outputs[0], emit_socket)
        else:
            print(f"WARNING: Could not find 'Emission' socket on OctaneDiffuseMaterial for {ldata.name}.") # Debug help
        
        # Diffuse Material (output 0) -> Light Output (input 'Surface' / index 0)
        nt.links.new(diff_mat.outputs[0], out_node.inputs['Surface'])
        
        # Set Power on Texture Emission node
        if 'Power' in emit.inputs: tex_emit.inputs['Power'].default_value = settings_group.power
        elif len(emit.inputs) > 1: tex_emit.inputs[1].default_value = settings_group.power # Fallback
        
        # Create Blender Object
        lobj = bpy.data.objects.new(name=lname, object_data=ldata)
        col.objects.link(lobj) # Link to our dedicated collection
        lobj.location = loc
        
        # Store metadata as custom properties for live updates and identification
        lobj["studio_role"] = role
        lobj["studio_style"] = style
        
        # Add Track To constraint to point at the target
        const = lobj.constraints.new('TRACK_TO')
        const.target = target
        const.track_axis = 'TRACK_NEGATIVE_Z' # Light's -Z axis points towards target
        const.up_axis = 'UP_Y' # Maintain light's local Y as Up
        
        # Apply initial On/Off state
        is_hidden = not settings_group.enabled
        lobj.hide_viewport = is_hidden
        lobj.hide_render = is_hidden

    # 2. Build lights based on selected style and toggles
    build_light('KEY', props.key_light)
    if props.use_fill: build_light('FILL', props.fill_light)
    if props.use_rim: build_light('RIM', props.rim_light)

    # 3. Add Backdrop if toggled
    # The dedicated operator `OCTANESTUDIO_OT_AddBackdrop` is used for this to prevent re-creation logic
    # within the main build function and allow separate control.
    # User will click the button directly.

# ------------------------------------------------------------------------
#   PANEL (UI Layout)
# ------------------------------------------------------------------------

class VIEW3D_PT_OctaneStudio(bpy.types.Panel):
    bl_label = "Octane Studio" # Display name in Blender UI
    bl_idname = "VIEW3D_PT_OctaneStudio"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Octane Studio" # Name of the tab in the N-panel

    def draw(self, context):
        layout = self.layout
        props = context.scene.octane_studio_props
        
        # Main Tab Layout
        row = layout.row(align=True)
        row.prop_enum(props, "ui_tab", 'CREATE', icon='SCENE')
        row.prop_enum(props, "ui_tab", 'CONTROL', icon='MOD_CLOTH')
        row.prop_enum(props, "ui_tab", 'TOOLS', icon='TOOL_SETTINGS')
        
        layout.separator() # Visual separator between tabs and content

        # --- TAB: CREATE ---
        if props.ui_tab == 'CREATE':
            box = layout.box() # Group settings within a box
            box.label(text="Setup Configuration", icon='PREFERENCES')
            box.prop(props, "target_object", icon='OBJECT_DATA', text="Light Target")
            box.prop(props, "setup_type", text="Style", description="Select the base lighting style.")
            
            row = box.row() # Group toggles in a row
            row.prop(props, "use_fill", text="Add Fill Light", description="Toggle creation of a fill light.")
            row.prop(props, "use_rim", text="Add Rim Light", description="Toggle creation of a rim/back light.")
            
            box.separator()
            row = box.row()
            row.scale_y = 1.5 # Make buttons larger for prominence
            row.operator("octanestudio.generate", icon='PLAY', text="Create Lighting")
            row.operator("octanestudio.clear", icon='TRASH', text="Clear") # Clear button in Create tab

        # --- TAB: CONTROL ---
        elif props.ui_tab == 'CONTROL':
            
            # Helper function to draw individual light control panels
            def draw_light_panel(layout, title, settings_prop):
                box = layout.box()
                row = box.row()
                # Expand/Collapse Toggle
                row.prop(settings_prop, "expanded", icon="TRIA_DOWN" if settings_prop.expanded else "TRIA_RIGHT", icon_only=True, emboss=False)
                # On/Off Toggle and Title
                row.prop(settings_prop, "enabled", text=title, icon='LIGHT')
                
                if settings_prop.expanded:
                    col = box.column(align=True)
                    col.enabled = settings_prop.enabled # Dim controls if light is off
                    
                    col.prop(settings_prop, "power", description="Adjust the light's power/intensity.")
                    col.prop(settings_prop, "distance", description="Adjust the light's distance from the target (multiplies base offset).")
                    col.prop(settings_prop, "size", text="Softness", description="Adjust the physical size of the light, affecting shadow sharpness.")
                    
                    split = col.split(factor=0.4) # Split row for label and property
                    split.label(text="Color Mode:")
                    split.prop(settings_prop, "use_kelvin", text="Kelvin", toggle=True, description="Switch between RGB color picker and Kelvin temperature slider.")
                    
                    if settings_prop.use_kelvin:
                        col.prop(settings_prop, "kelvin", description="Set color temperature in Kelvin (1000K=warm, 12000K=cool).")
                    else:
                        col.prop(settings_prop, "color", text="", description="Set the light's color using RGB values.")

            # Draw panels for Key, Fill, and Rim lights based on creation toggles
            draw_light_panel(layout, "Key Light", props.key_light)
            
            if props.use_fill: # Only draw fill light panel if it was enabled during creation
                draw_light_panel(layout, "Fill Light", props.fill_light)
            if props.use_rim: # Only draw rim light panel if it was enabled during creation
                draw_light_panel(layout, "Rim Light", props.rim_light)
                
            layout.separator()
            layout.operator("octanestudio.sync_ui", icon='FILE_REFRESH', text="Sync UI from Scene", description="Updates the UI sliders to match current light settings in the scene (if manually modified).")

        # --- TAB: TOOLS ---
        elif props.ui_tab == 'TOOLS':
            
            # CAMERA CONTROL BOX
            cam = get_portrait_cam()
            box = layout.box()
            box.label(text="Camera", icon='CAMERA_DATA')
            
            if not cam: # Show Add Camera button if camera doesn't exist
                box.operator("octanestudio.add_camera", icon='ADD', text="Add Portrait Cam", description="Create an 85mm portrait camera and set it as active.")
            else: # Show camera controls if camera exists
                row = box.row()
                row.label(text="Portrait Cam Active", icon='CHECKMARK')
                row.prop(props, "camera_locked", text="Lock to Target", toggle=True, icon='CONSTRAINT', description="Toggle camera constraint to orbit target. Disable to move camera freely.")
                
                # Camera Target Picker (new in v2.2)
                box.prop(props, "camera_target", icon='OBJECT_DATA', description="Select a specific object for the camera to focus on. If empty, uses the main 'Light Target'.")

                col = box.column(align=True)
                col.enabled = props.camera_locked # Only enable these controls if camera is locked
                col.prop(props, "camera_dist", description="Adjust the camera's distance from its focus target.")
                col.prop(props, "camera_height", description="Adjust the camera's vertical position relative to its focus target.")
                col.prop(props, "camera_orbit", description="Orbit the camera around its focus target.")
                if not props.camera_locked:
                    col.label(text="Move manually in Viewport (G, R, S keys)", icon='INFO')

            # PRESETS BOX
            box = layout.box()
            box.label(text="Presets", icon='PRESET')
            row = box.row(align=True)
            row.operator("octanestudio.save_preset", icon='IMPORT', text="Save", description="Save current light settings as an internal preset.")
            row.operator("octanestudio.load_preset", icon='EXPORT', text="Load", description="Load previously saved light settings.")
            box.operator("octanestudio.reset_values", icon='LOOP_BACK', text="Reset to Defaults", description="Reset all light power, color, distance, and size values to factory defaults.")
            
            # ENVIRONMENT BOX
            box = layout.box()
            box.label(text="Environment", icon='SCENE_DATA')
            box.operator("octanestudio.add_backdrop", icon='MESH_PLANE', text="Add Backdrop", description="Add a simple curved studio backdrop to the scene.")
            box.operator("octanestudio.studio_black", icon='WORLD', text="Set Studio Black", description="Set the Blender World background to pure black (0 strength).")

# ------------------------------------------------------------------------
#   REGISTRATION
# ------------------------------------------------------------------------

classes = (
    LightSettings,
    OctaneStudioProperties,
    OCTANESTUDIO_OT_Generate,
    OCTANESTUDIO_OT_Clear,
    OCTANESTUDIO_OT_SavePreset,
    OCTANESTUDIO_OT_LoadPreset,
    OCTANESTUDIO_OT_ResetValues,
    OCTANESTUDIO_OT_AddBackdrop,
    OCTANESTUDIO_OT_AddCamera,
    OCTANESTUDIO_OT_StudioBlack,
    OCTANESTUDIO_OT_SyncUI,
    VIEW3D_PT_OctaneStudio,
)

def register():
    """Registers all classes and properties when the add-on is enabled."""
    for cls in classes:
        bpy.utils.register_class(cls)
    # Register the main property group to the scene
    bpy.types.Scene.octane_studio_props = bpy.props.PointerProperty(type=OctaneStudioProperties)

def unregister():
    """Unregisters all classes and properties when the add-on is disabled."""
    for cls in reversed(classes): # Unregister in reverse order
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.octane_studio_props # Delete the main property group

if __name__ == "__main__":
    register()
