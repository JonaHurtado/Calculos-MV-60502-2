
import streamlit as st
import pandas as pd
import math
from calculations import (
    get_k1, get_k2, get_k3, get_k4, calculate_ib, interpolate_linear
)
from data_tables import AMPACITY_DB, VALID_SECTIONS, MAX_TEMPERATURES

st.set_page_config(page_title="Cálculos MV IEC 60502", layout="wide", page_icon="⚡")

# --- Introduction & footer ---
st.title("⚡ Cálculos de Cables de Media Tensión (IEC 60502)")
st.markdown("""
**Bienvenido a la herramienta de cálculo de cables de Media Tensión.**

Esta aplicación permite dimensionar y verificar cables subterráneos según la norma **IEC 60502-2**.
Simplemente defina las condiciones del terreno, las características del sistema eléctrico y luego añada los circuitos y tramos necesarios.

**Conceptos Clave:**
- **Circuito**: Conjunto de fases (L1, L2, L3) que transportan energía desde un origen común. Puede tener varios tramos.
- **Tramo**: Sección física del circuito con características homogéneas (longitud, tipo de cable, instalación). La potencia se acumula a lo largo de los tramos.
""")
st.markdown("---")

# Sidebar - Global Parameters
st.sidebar.header("🌍 1. Características del Terreno")
temp_ground = st.sidebar.number_input("Temperatura del Terreno (ºC) 🌡️", value=20.0, step=1.0)
resistivity_ground = st.sidebar.number_input("Resistividad Térmica (K·m/W) 🏜️", value=1.5, step=0.1)

st.sidebar.header("⚡ 2. Sistema Eléctrico")
voltage_sys = st.sidebar.number_input("Tensión de Operación (kV)", value=30.0, step=0.5)
frequency = st.sidebar.number_input("Frecuencia (Hz)", value=50.0, step=5.0)
pf = st.sidebar.number_input("Factor de Potencia (FP)", value=0.9, max_value=1.0, step=0.01)
oversizing = st.sidebar.number_input("Sobredimensionamiento (%) 📈", value=0.0, step=1.0)

# Main Area - Circuit Definition
st.header("📋 Definición de Circuitos y Tramos")

if "circuits" not in st.session_state:
    st.session_state.circuits = []

# Helper functions for state management
def add_circuit():
    st.session_state.circuits.append({"sections": []})

def remove_circuit(index):
    st.session_state.circuits.pop(index)

def add_section(circuit_index):
    st.session_state.circuits[circuit_index]["sections"].append({
        "pb_power": 10120.0,
        "install_type": "Directamente enterrado",
        "insulation": "XLPE",
        "section_mm2": 400,
        "conductor": "Al",
        "voltage_u0": "18/30 (36) kV",
        "layout": "Trefoil",
        "armour": False,
        "core_type": "Single Core",
        "veins": 1,
        "length": 10061.0,
        "parallel_circuits": 4, # n circuits in group
        "spacing": 200.0,
        "depth": 0.8
    })

def remove_section(circuit_index, section_index):
    st.session_state.circuits[circuit_index]["sections"].pop(section_index)

col_add, _ = st.columns([1, 4])
if col_add.button("➕ Añadir Nuevo Circuito"):
    add_circuit()

# Display Circuits
for i in range(len(st.session_state.circuits)):
    if i >= len(st.session_state.circuits): break
    
    circuit = st.session_state.circuits[i]
    
    st.markdown("---")
    c_col1, c_col2 = st.columns([4, 1])
    c_col1.subheader(f"🔌 Circuito {i+1}")
    
    if c_col2.button(f"🗑️ Eliminar Circuito {i+1}", key=f"del_circ_{i}"):
        remove_circuit(i)
        st.rerun()
    
    # Add Section to Circuit
    if st.button(f"➕ Añadir Tramo al Circuito {i+1}", key=f"btn_add_sec_{i}"):
        add_section(i)
        st.rerun()

    # Sections Inputs
    cumulative_power = 0
    
    for j in range(len(circuit["sections"])):
        if j >= len(circuit["sections"]): break
        
        section = circuit["sections"][j]
        
        st.markdown(f"**🛣️ Tramo {j+1}**")
        
        with st.expander(f"⚙️ Configuración Tramo {j+1}", expanded=True):
            # Header with delete button
            h_col1, h_col2 = st.columns([6, 1])
            with h_col2:
                if st.button(f"🗑️", key=f"del_sec_{i}_{j}", help="Eliminar este tramo"):
                    remove_section(i, j)
                    st.rerun()
                    
            col1, col2, col3 = st.columns(3)
            
            with col1:
                section["pb_power"] = st.number_input(f"Potencia PB (kVA)", value=section["pb_power"], key=f"pb_{i}_{j}")
                
                current_section_power = section["pb_power"] + cumulative_power
                cumulative_power = current_section_power
                
                st.info(f"⚡ Potencia Acumulada de Diseño: {current_section_power} kVA")
                
                section["install_type"] = st.selectbox("Tipo Instalación 🏗️", ["Directamente enterrado", "Enterrado bajo tubo"], index=0 if section["install_type"]=="Directamente enterrado" else 1, key=f"inst_{i}_{j}")
                section["depth"] = st.number_input("Profundidad (m) ⬇️", value=section["depth"], key=f"dep_{i}_{j}")

            with col2:
                section["insulation"] = st.selectbox("Aislamiento 🛡️", ["EPR", "HEPR", "XLPE"], index=2, key=f"ins_{i}_{j}")
                section["section_mm2"] = st.selectbox("Sección (mm²) 📏", VALID_SECTIONS, index=VALID_SECTIONS.index(section["section_mm2"]) if section["section_mm2"] in VALID_SECTIONS else 12, key=f"sec_{i}_{j}")
                section["conductor"] = st.selectbox("Conductor 🧱", ["Al", "Cu"], index=0 if section["conductor"]=="Al" else 1, key=f"cond_{i}_{j}")
                section["voltage_u0"] = st.selectbox("Tensión Aislamiento Um ⚡", ["3,6/6 (7,2)", "6/10 (12)", "8,7/15 (17,5)", "12/20 (24)", "18/30 (36) kV"], index=4, key=f"u0_{i}_{j}")

            with col3:
                 section["layout"] = st.selectbox("Disposición 📐", ["Trefoil", "Flat spaced", "Flat touching ducts"], index=0, key=f"lay_{i}_{j}")
                 section["core_type"] = st.selectbox("Tipo Cable 🧵", ["Single Core", "Three Core"], index=0 if section["core_type"]=="Single Core" else 1, key=f"core_{i}_{j}")
                 section["parallel_circuits"] = st.number_input("Circuitos en Paralelo (En la zanja) 🔢", value=section["parallel_circuits"], min_value=1, key=f"par_{i}_{j}")
                 section["spacing"] = st.number_input("Separación entre circuitos (mm) ↔️", value=section["spacing"], key=f"spa_{i}_{j}")
            
            section["armour"] = st.checkbox("¿Tiene Armadura? 🛡️", value=section["armour"], key=f"arm_{i}_{j}")

# --- Calculation & Reporting ---
st.markdown("---")

if st.button("🚀 Calcular Ampacidad", type="primary"):
    st.markdown("## 📊 Resultados del Cálculo")
    
    if not st.session_state.circuits:
        st.warning("⚠️ No hay circuitos definidos.")
    
    for i, circuit in enumerate(st.session_state.circuits):
        st.markdown(f"### 🔌 Circuito {i+1}")
        
        cumulative_p = 0
        if not circuit["sections"]:
            st.info("ℹ️ Circuito sin tramos.")
            continue

        for j, section in enumerate(circuit["sections"]):
            # Calc Power
            cumulative_p += section["pb_power"]
            design_power = cumulative_p
            
            # 1. Calc Ib
            ib = calculate_ib(design_power, voltage_sys, pf, oversizing)
            
            # 2. Get Factors
            k1, src_k1 = get_k1(temp_ground, section["insulation"])
            k2, src_k2 = get_k2(section["depth"], section["section_mm2"], section["install_type"])
            k3, src_k3 = get_k3(resistivity_ground, section["install_type"], section["core_type"], section["section_mm2"])
            k4, src_k4 = get_k4(section["parallel_circuits"], section["spacing"], section["install_type"], section["core_type"])
            
            # 3. Base Ampacity (Iz)
            # Map insulation types - HEPR uses EPR values
            if section["insulation"] == "HEPR":
                db_ins = "EPR"
            else:
                db_ins = section["insulation"]  # EPR or XLPE
            
            db_cond = section["conductor"]
            db_core = section["core_type"]
            
            # Map installation type to database keys
            # "Directamente enterrado" -> "Direct"
            # "Enterrado bajo tubo" -> "Ducts"
            if section["install_type"] == "Directamente enterrado":
                db_inst = "Direct"
            elif section["install_type"] == "Enterrado bajo tubo":
                db_inst = "Ducts"
            # Armor parameter logic based on cable type per IEC 60502-2:
            # - Single Core (Tables B.2-B.5): ampacity does NOT distinguish by armor
            # - Three Core (Tables B.6-B.9): ampacity DOES distinguish by armor
            if section["core_type"] == "Single Core":
                # Single Core cables: always use "Unarmoured" for ampacity lookup
                db_armor = "Unarmoured"
            else:
                # Three Core cables: use actual armor selection
                db_armor = "Armoured" if section["armour"] else "Unarmoured"
            
            # Map layout - Single Core cables have different ampacities by layout
            # Three Core cables use "N/A" as they don't have layout distinctions
            if section["core_type"] == "Single Core":
                layout_selection = section.get("layout", "Trefoil")
                if layout_selection == "Trefoil":
                    db_layout = "Trefoil"
                elif layout_selection == "Flat spaced":
                    db_layout = "Flat Spaced"
                elif layout_selection == "Flat touching ducts":
                    db_layout = "Flat Touching"
                else:
                    db_layout = "Trefoil"  # Default conservative
            else:
                # Three Core cables don't have layout distinction in IEC tables
                db_layout = "N/A"
            
            try:
                # Use robust lookup with 6-tuple key
                # key is (Ins, Cond, Core, Install, Armoring, Layout)
                record = AMPACITY_DB.get((db_ins, db_cond, db_core, db_inst, db_armor, db_layout))
                if record:
                    base_iz = record["data"].get(section["section_mm2"], 0)
                    source_table = record["source"]
                else:
                    base_iz = 0
                    source_table = "Desconocida"
                
                if base_iz == 0:
                    st.error(f"❌ No se encontró ampacidad base en DB para los parámetros seleccionados en el tramo {j+1}.")

            except Exception as e:
                base_iz = 0
                source_table = "Error"
                st.error(f"Error lookup: {e}")
            
            # 4. Corrected Iz'
            iz_prime = base_iz * k1 * k2 * k3 * k4
            
            # 5. Verification
            passed = ib <= iz_prime
            status_color = "green" if passed else "red"
            status_icon = "✅" if passed else "❌"
            
            # Display Report
            with st.container():
                st.markdown(f"#### 🛣️ Tramo {j+1} | {design_power} kVA | Resultado: {status_icon}")
                
                r_col1, r_col2, r_col3 = st.columns(3)
                r_col1.metric("Corriente Diseño (Ib)", f"{ib:.2f} A")
                r_col2.metric("Ampacidad Corregida (Iz')", f"{iz_prime:.2f} A", delta=f"{iz_prime-ib:.2f} A", delta_color="normal" if passed else "inverse")
                r_col3.metric("Ampacidad Base (Iz)", f"{base_iz} A", help=f"Fuente: {source_table}")
                
                with st.expander("📝 Detalles de Factores de Corrección"):
                    f_df = pd.DataFrame({
                        "Factor": ["K1 (Temp)", "K2 (Profundidad)", "K3 (Resistividad)", "K4 (Agrupamiento)"],
                        "Valor": [f"{k1:.3f}", f"{k2:.3f}", f"{k3:.3f}", f"{k4:.3f}"],
                        "Fuente": [src_k1, src_k2, src_k3, src_k4],
                        "Input Usuario": [f"{temp_ground} ºC", f"{section['depth']} m", f"{resistivity_ground} K·m/W", f"{section['parallel_circuits']} circs @ {section['spacing']} mm"]
                    })
                    st.table(f_df)
                
                if not passed:
                    st.error(f"⚠️ **VALIDACIÓN FALLIDA**: El cable NO CUMPLE. La corriente de diseño ({ib:.2f} A) es MAYOR que la ampacidad corregida ({iz_prime:.2f} A).")
                else:
                    st.success("✅ **VALIDACIÓN EXITOSA**: El cable CUMPLE con los requisitos de ampacidad calculada.")
            
            st.divider()

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("👨‍💻 Desarrollado por **Jonathan Hurtado Moreira**")
