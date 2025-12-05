# Octane Studio Lighting Add-on for Blender

**Version:** 1.0.0
**Author:** TrevisCloud

A professional Blender add-on designed to streamline studio lighting and camera setup specifically for OctaneRender. Quickly create and control classic portrait lighting styles with real-time feedback, individual light adjustments, customizable color temperatures, and smart camera tools.

---

## ✨ Features

- **3 Classic Lighting Styles:**
  - **Low Key:** Dramatic, high-contrast, moody lighting.
  - **Butterfly Lighting:** Classic beauty lighting with a distinctive shadow under the nose.
  - **Side / Split Lighting:** Divides the subject's face into light and shadow for intense drama.
- **Per-Light Control:** Adjust Power, RGB/Kelvin Color, Distance, and Size (Softness) for Key, Fill, and Rim lights individually.
- **Real-time Updates:** Sliders instantly update the lights in your viewport without needing to re-create the setup.
- **On/Off Toggles:** Toggle individual lights on or off to isolate effects or save render time.
- **Kelvin Temperature:** Seamlessly switch between RGB color picking and accurate Kelvin temperature control (1000K to 12000K).
- **Smart Target Picking:** Define a main target object for your lights to follow, and a separate focus target for your camera.
- **Preset System:** Save and load your favorite light configurations (including on/off states and all parameters) within your Blender session.
- **Studio Backdrop:** One-click button to add a simple, curved studio background.
- **Portrait Camera Tool:**
  - Add a pre-configured 85mm camera.
  - **Locked Mode:** Orbit, adjust distance, and height around your target with dedicated sliders.
  - **Free Mode:** Disable locking to manually position the camera.
- **Environment Control:** Quick button to set your Blender World background to pure black for a clean studio look.
- **UI Sync:** Refresh the add-on's UI sliders to match any manual changes made directly in the Shader Editor.
- **Clean Scene Management:** All generated lights and objects are grouped in a dedicated collection for easy organization and quick cleanup.

---

## 🚀 Installation

1.  **Download:** Download the `octane_studio_lighting.zip` file.
2.  **Blender:** Open Blender.
3.  Go to `Edit > Preferences > Add-ons`.
4.  Click **"Install..."** and navigate to the downloaded `.zip` file.
5.  **Enable:** Once installed, ensure the checkbox next to **"Octane Studio Lighting"** is enabled.

---

## 💡 How to Use

1.  **Select Your Subject:** In the 3D Viewport, select the object (e.g., your character's head or a bust) that you want to light. This will be the initial target for your lights. (You can also pick a different target later in the "Create" tab).
2.  **Open the Panel:** In the 3D Viewport, press the **`N` key** to open the sidebar. Find the **"Octane Studio"** tab.
3.  **Navigate Tabs:** The add-on is organized into three tabs:
    - **CREATE:** For generating new lighting setups.
    - **CONTROL:** For fine-tuning individual lights in real-time.
    - **TOOLS:** For camera, presets, and environment helpers.

### 1. CREATE Tab

- **Light Target:** (Eyedropper) Select the object that your lights should focus on. If left empty, a "Studio_Target_Null" will be created at your scene's origin.
- **Style:** Choose between "Low Key", "Butterfly", or "Side/Split" lighting.
- **Add Fill Light / Add Rim Light:** Toggle these options to include or exclude these secondary lights in your generated setup.
- **Create Lighting:** Click this button to generate the chosen lighting style. It will clear any previously generated studio lights and apply the new setup.
- **Clear Lights:** Removes all lights, the target null (if created by the add-on), and the backdrop associated with the add-on.

### 2. CONTROL Tab

This tab provides real-time sliders for each light in your scene.

- **Key Light / Fill Light / Rim Light:** Each light has its own collapsible panel.
  - **Expand/Collapse Arrow:** Click the arrow next to the light's name to show/hide its controls.
  - **Enable Checkbox:** Toggle the light On/Off in both the viewport and render. When off, its controls are dimmed.
  - **Power:** Adjust the intensity of the light.
  - **Distance:** Adjusts the light's distance from the target.
  - **Size (Softness):** Controls the physical size of the light. Larger lights create softer shadows.
  - **Kelvin Mode Toggle:** Switch between RGB color picking and Kelvin temperature input.
    - **RGB:** Use the color picker to select a color.
    - **Temp (K):** Input a Kelvin temperature (e.g., 2700K for warm, 6500K for daylight, 9000K for cool).
- **Sync UI from Scene:** If you manually adjust light nodes in Blender's Shader Editor, click this button to refresh the add-on's UI sliders to match the scene's current values.

### 3. TOOLS Tab

This tab contains utilities for cameras, presets, and the environment.

- **Camera Section:**
  - **Add Portrait Cam:** Creates an 85mm camera, sets it active, and locks it to your chosen `Focus Target`.
  - **Portrait Cam Active:** (Indicator) Shows if the add-on's camera is in your scene.
  - **Focus Target:** (Eyedropper) Select a specific object for the camera to look at and orbit. If empty, the camera will use the main `Light Target`.
  - **Lock to Target:** Toggle this to enable/disable the camera's tracking constraint. When disabled, you can move the camera freely using Blender's G, R, S keys.
  - **Cam Distance:** Adjusts how far the camera is from its `Focus Target`.
  - **Cam Height:** Adjusts the camera's vertical position relative to its `Focus Target`.
  - **Orbit Angle:** Rotates the camera around its `Focus Target`.
- **Presets Section:**
  - **Save Preset:** Stores the current Power, Color, Distance, Size, and On/Off states of all your lights. This preset is saved within your Blender session.
  - **Load Preset:** Applies your saved preset to the lights in the scene.
  - **Reset to Defaults:** Resets all light parameters (Power, Color, Distance, Size) to their default factory values.
- **Environment Section:**
  - **Add Backdrop:** Creates a simple curved backdrop (a plane rotated as a wall) behind your `Light Target`.
  - **Set Studio Black:** Sets your Blender World background to pure black with zero strength, ideal for studio lighting.

---

## ⚠️ Important Notes

- **OctaneRender:** This add-on is designed specifically for **OctaneRender for Blender**. Ensure Octane is selected as your render engine (`Render Properties > Render Engine`) for correct functionality.
- **Node Changes:** Switching the "Use Kelvin" toggle for a light changes the node type (RGB Color vs. Blackbody). For this change to take effect, you must click **"Create Lighting"** again after toggling. Other slider adjustments update in real-time.
- **Cleanup:** Always use the "Clear Lights" button to properly remove all generated objects.

---

## 🐞 Troubleshooting

- **"Lights not updating in real-time":**
  - Ensure Octane is selected as your render engine.
  - Confirm your scene has a light setup generated by the add-on.
  - If you've manually edited the light nodes, try "Sync UI from Scene" in the Control tab.
- **"Error: bl_idname 'octanestudio.generate' has been registered before":**
  - This typically means you have multiple versions of the add-on installed or are running the script directly multiple times. Restart Blender or disable/enable the add-on in preferences.
- **"Backdrop already exists":**
  - The add-on prevents duplicate backdrops. If you want a new one, use "Clear Lights" first or delete the existing "Backdrop" object manually.
- **"Camera not moving":**
  - Ensure "Portrait_Cam" exists in your scene.
  - Check if "Lock to Target" is enabled in the Camera section. If not, you need to move it manually.
  - Ensure your `Focus Target` or `Light Target` is a valid object.

---

## ❤️ Support

For questions, bug reports, or feature requests, please [contact the author: www.linkedin.com/in/trevisacloud / visit GitHub: github.com/TrevisCloud].

---
