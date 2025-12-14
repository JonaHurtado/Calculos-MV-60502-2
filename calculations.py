
# calculations.py
# Logic for IEC 60502-2 MV Cable Calculations

import math
from data_tables import (
    TABLE_B11, TABLE_B12, TABLE_B13, 
    TABLE_B14, TABLE_B15, TABLE_B16, TABLE_B17, 
    TABLE_B18_DATA, TABLE_B19_DATA, TABLE_B20_DATA, TABLE_B21_DATA
)

def interpolate_linear(x, x1, y1, x2, y2):
    """Linear interpolation."""
    if x2 == x1: return y1
    return y1 + (x - x1) * (y2 - y1) / (x2 - x1)

def get_k1(temp_ground, insulation_type):
    """
    Calculate K1 - Soil Temperature Factor (Table B.11).
    Column 0: PVC (70°C max temp) - NOT USED ANYMORE
    Column 1: EPR/HEPR/XLPE (90°C max temp)
    """
    # All supported insulations (EPR, HEPR, XLPE) use column 1 (90°C)
    idx = 1
    
    temps = sorted(TABLE_B11.keys())
    
    if temp_ground <= temps[0]:
        t1, t2 = temps[0], temps[1]
    elif temp_ground >= temps[-1]:
        t1, t2 = temps[-2], temps[-1]
    else:
        for i in range(len(temps)-1):
            if temps[i] <= temp_ground <= temps[i+1]:
                t1, t2 = temps[i], temps[i+1]
                break
                
    y1 = TABLE_B11[t1][idx]
    y2 = TABLE_B11[t2][idx]
    
    return interpolate_linear(temp_ground, t1, y1, t2, y2), "Table B.11"

def get_k2(depth, section, installation_type):
    """
    Calculate K2 - Burial Depth Factor (Table B.12/B.13).
    """
    is_direct = (installation_type == "Directamente enterrado")
    table = TABLE_B12 if is_direct else TABLE_B13
    table_name = "Table B.12" if is_direct else "Table B.13"
    
    idx = 0 if section <= 185 else 1
    
    depths = sorted(table.keys())
    
    if depth <= depths[0]:
        d1, d2 = depths[0], depths[1]
    elif depth >= depths[-1]:
        d1, d2 = depths[-2], depths[-1]
    else:
        for i in range(len(depths)-1):
            if depths[i] <= depth <= depths[i+1]:
                d1, d2 = depths[i], depths[i+1]
                break
    
    y1 = table[d1][idx]
    y2 = table[d2][idx]
    
    return interpolate_linear(depth, d1, y1, d2, y2), table_name

def get_k3(resistivity, installation_type, cable_core_type, section):
    """
    Calculate K3 - Soil Thermal Resistivity Factor.
    Tables B.14 - B.17
    Now with section-aware interpolation.
    """
    is_single = (cable_core_type == "Single Core")
    is_direct = (installation_type == "Directamente enterrado")
    
    if is_single and is_direct:
        table = TABLE_B14; table_name = "Table B.14"
    elif is_single and not is_direct:
        table = TABLE_B15; table_name = "Table B.15"
    elif not is_single and is_direct:
        table = TABLE_B16; table_name = "Table B.16"
    else:
        table = TABLE_B17; table_name = "Table B.17"
    
    # Get available sections in the table
    sections = sorted(table.keys())
    
    # Step 1: Select or interpolate by section
    if section <= sections[0]:
        # Use smallest section
        section_data = table[sections[0]]
    elif section >= sections[-1]:
        # Use largest section
        section_data = table[sections[-1]]
    elif section in sections:
        # Exact section match
        section_data = table[section]
    else:
        # Interpolate between two sections
        # Find bounding sections
        s1, s2 = None, None
        for i in range(len(sections)-1):
            if sections[i] < section < sections[i+1]:
                s1, s2 = sections[i], sections[i+1]
                break
        
        if s1 is None:  # Shouldn't happen but safety check
            section_data = table[sections[0]]
        else:
            # Get resistivity values (should be same for all sections)
            resistivities = sorted(table[s1].keys())
            
            # Interpolate factor for each resistivity point
            section_data = {}
            for r in resistivities:
                f1 = table[s1][r]
                f2 = table[s2][r]
                section_data[r] = interpolate_linear(section, s1, f1, s2, f2)
    
    # Step 2: Interpolate by resistivity within the selected/interpolated section data
    resistivities = sorted(section_data.keys())
    
    if resistivity <= resistivities[0]:
        r1, r2 = resistivities[0], resistivities[1]
    elif resistivity >= resistivities[-1]:
        r1, r2 = resistivities[-2], resistivities[-1]
    else:
        r1, r2 = resistivities[0], resistivities[1]  # default
        for i in range(len(resistivities)-1):
            if resistivities[i] <= resistivity <= resistivities[i+1]:
                r1, r2 = resistivities[i], resistivities[i+1]
                break
    
    y1 = section_data[r1]
    y2 = section_data[r2]
    
    return interpolate_linear(resistivity, r1, y1, r2, y2), table_name

def get_k4(num_circuits, spacing, installation_type, cable_core_type):
    """
    Calculate K4 - Grouping Factor.
    """
    # FIX: If 1 circuit, K4 is 1.00
    if num_circuits <= 1:
        return 1.0, "N/A (Single Circuit)"

    # Select the appropriate K4 table based on cable type and installation method
    # Table B.18: Three-core cables laid direct in ground
    # Table B.19: Single-core cables (three-phase circuits) laid direct in ground
    # Table B.20: Three-core cables in single-way ducts
    # Table B.21: Single-core cables (three-phase circuits) in single-way ducts
    
    is_single = (cable_core_type == "Single Core")
    is_direct = (installation_type == "Directamente enterrado")
    
    if is_single and is_direct:
        table = TABLE_B19_DATA
        table_name = "Table B.19"
    elif is_single and not is_direct:  # In ducts
        table = TABLE_B21_DATA
        table_name = "Table B.21"
    elif not is_single and is_direct:  # Three core, direct
        table = TABLE_B18_DATA
        table_name = "Table B.18"
    else:  # Three core, in ducts
        table = TABLE_B20_DATA
        table_name = "Table B.20"
    
    circuits = sorted(table.keys())
    
    def get_factor_for_row(n_circ, s_dist):
        if n_circ not in table: return None 
        row_data = table[n_circ]
        
        # Filter out None values and get valid spacings
        valid_spacings = sorted([k for k, v in row_data.items() if v is not None])
        
        if not valid_spacings:
            return None
        
        # If only one valid spacing, return that value
        if len(valid_spacings) == 1:
            return row_data[valid_spacings[0]]
        
        if s_dist <= valid_spacings[0]:
            s1, s2 = valid_spacings[0], valid_spacings[1]
        elif s_dist >= valid_spacings[-1]:
            s1, s2 = valid_spacings[-2], valid_spacings[-1]
        else:
            s1, s2 = valid_spacings[0], valid_spacings[1]  # default
            for i in range(len(valid_spacings)-1):
                if valid_spacings[i] <= s_dist <= valid_spacings[i+1]:
                    s1, s2 = valid_spacings[i], valid_spacings[i+1]
                    break
        
        v1 = row_data[s1]
        v2 = row_data[s2]
        return interpolate_linear(s_dist, s1, v1, s2, v2)

    if num_circuits <= circuits[0]:
        c1, c2 = circuits[0], circuits[1]
    elif num_circuits >= circuits[-1]:
        c1, c2 = circuits[-2], circuits[-1]
    else:
        # Check if exact
        if num_circuits in circuits:
            return get_factor_for_row(num_circuits, spacing), table_name
        
        for i in range(len(circuits)-1):
            if circuits[i] <= num_circuits <= circuits[i+1]:
                c1, c2 = circuits[i], circuits[i+1]
                break
                
    f1 = get_factor_for_row(c1, spacing)
    f2 = get_factor_for_row(c2, spacing)
    
    # Handle None values
    if f1 is None or f2 is None:
        # Use the non-None value if available, or return a conservative estimate
        if f1 is not None:
            return f1, table_name
        elif f2 is not None:
            return f2, table_name
        else:
            # Very conservative: assume touching (worst case)
            return 0.50, f"{table_name} (estimated - data not available)"
    
    return interpolate_linear(num_circuits, c1, f1, c2, f2), table_name

def calculate_ib(power_kva, voltage_kv, pf, oversizing_pct):
    if pf == 0 or voltage_kv == 0: return 0
    base_current = power_kva / (math.sqrt(3) * voltage_kv * pf)
    return base_current * (1 + oversizing_pct/100)
