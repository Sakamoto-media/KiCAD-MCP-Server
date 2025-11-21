from skip import Schematic
# Symbol class might not be directly importable in the current version
import os
import uuid
import sexpdata

class ComponentManager:
    """Manage components in a schematic"""

    # KiCAD symbol library paths
    KICAD_SYMBOL_LIB_PATH = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"

    @staticmethod
    def _load_symbol_from_library(lib_id: str):
        """Load symbol definition from KiCAD library

        Args:
            lib_id: Library ID in format "Library:Symbol" (e.g., "Device:C")

        Returns:
            S-expression list for the symbol definition, or None if not found
        """
        try:
            # Parse lib_id
            if ':' not in lib_id:
                print(f"Invalid lib_id format: {lib_id}")
                return None

            library_name, symbol_name = lib_id.split(':', 1)
            lib_file = os.path.join(ComponentManager.KICAD_SYMBOL_LIB_PATH, f"{library_name}.kicad_sym")

            if not os.path.exists(lib_file):
                print(f"Library file not found: {lib_file}")
                return None

            # Read and parse library file
            with open(lib_file, 'r', encoding='utf-8') as f:
                lib_content = f.read()

            # Parse S-expression
            lib_sexpr = sexpdata.loads(lib_content)

            # Find the symbol definition
            # Library structure: (kicad_symbol_lib ... (symbol "SymbolName" ...) ...)
            if not isinstance(lib_sexpr, list):
                return None

            for item in lib_sexpr:
                if isinstance(item, list) and len(item) > 0:
                    if hasattr(item[0], 'value') and item[0].value() == 'symbol':
                        # Check if this is the symbol we're looking for
                        if len(item) > 1 and item[1] == symbol_name:
                            # Found it! Return the symbol definition
                            # Need to prepend it with the lib_id for the schematic
                            symbol_def = [sexpdata.Symbol('symbol'), lib_id] + item[2:]
                            print(f"Loaded symbol definition for {lib_id}")
                            return symbol_def

            print(f"Symbol {symbol_name} not found in library {library_name}")
            return None

        except Exception as e:
            print(f"Error loading symbol from library: {e}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def _ensure_symbol_in_lib_symbols(schematic: Schematic, lib_id: str):
        """Ensure symbol definition exists in lib_symbols section

        Args:
            schematic: Schematic object
            lib_id: Library ID (e.g., "Device:C")

        Returns:
            bool: True if symbol definition exists or was added, False on error
        """
        try:
            # Check if lib_symbols section exists and if symbol is already there
            lib_symbols_index = None
            lib_symbols_list = None

            for i, item in enumerate(schematic.tree):
                if isinstance(item, list) and len(item) > 0:
                    if hasattr(item[0], 'value') and item[0].value() == 'lib_symbols':
                        lib_symbols_index = i
                        lib_symbols_list = item
                        break

            if lib_symbols_list is None:
                print("lib_symbols section not found in schematic")
                return False

            # Check if symbol already exists
            for item in lib_symbols_list[1:]:  # Skip 'lib_symbols' symbol itself
                if isinstance(item, list) and len(item) > 1:
                    if hasattr(item[0], 'value') and item[0].value() == 'symbol':
                        if item[1] == lib_id:
                            print(f"Symbol {lib_id} already in lib_symbols")
                            return True

            # Symbol not found, load from library
            symbol_def = ComponentManager._load_symbol_from_library(lib_id)
            if symbol_def is None:
                return False

            # Add to lib_symbols section
            lib_symbols_list.append(symbol_def)
            print(f"Added {lib_id} to lib_symbols section")
            return True

        except Exception as e:
            print(f"Error ensuring symbol in lib_symbols: {e}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def _get_project_uuid(schematic: Schematic):
        """Extract project UUID from schematic"""
        try:
            # Look for project UUID in existing instances
            if hasattr(schematic, 'symbol') and len(schematic.symbol) > 0:
                first_symbol = schematic.symbol[0]
                if hasattr(first_symbol, 'instances'):
                    # Parse instances to get project path UUID
                    instances_str = str(first_symbol.instances)
                    # Extract UUID from path
                    import re
                    match = re.search(r'/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', instances_str)
                    if match:
                        return match.group(1)
            # Fallback: parse from tree directly
            if hasattr(schematic, 'tree') and isinstance(schematic.tree, list):
                for item in schematic.tree:
                    if isinstance(item, list) and len(item) > 0:
                        if hasattr(item[0], 'value') and item[0].value() == 'symbol':
                            # Search for instances in symbol
                            for subitem in item:
                                if isinstance(subitem, list) and len(subitem) > 0:
                                    if hasattr(subitem[0], 'value') and subitem[0].value() == 'instances':
                                        # Found instances, extract UUID
                                        instances_str = str(subitem)
                                        import re
                                        match = re.search(r'/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', instances_str)
                                        if match:
                                            return match.group(1)
        except Exception as e:
            print(f"Warning: Could not extract project UUID: {e}")
        # Return a new UUID if we can't find one
        return str(uuid.uuid4())

    @staticmethod
    def _create_property_sexpr(name: str, value: str, at_x: float, at_y: float, at_rot: int = 0,
                               hide: bool = False, justify: str = None):
        """Create a property S-expression"""
        effects_parts = [
            [sexpdata.Symbol('font'),
             [sexpdata.Symbol('size'), 1.27, 1.27]]
        ]

        if justify:
            effects_parts.append([sexpdata.Symbol('justify'), sexpdata.Symbol(justify)])

        if hide:
            effects_parts.append([sexpdata.Symbol('hide'), sexpdata.Symbol('yes')])

        property_expr = [
            sexpdata.Symbol('property'),
            name,
            value,
            [sexpdata.Symbol('at'), at_x, at_y, at_rot],
            [sexpdata.Symbol('effects')] + effects_parts
        ]

        return property_expr

    @staticmethod
    def _get_library_symbol_pins(schematic: Schematic, lib_id: str):
        """Get pin information from library symbol definition"""
        try:
            # Try to find the library symbol definition in the schematic tree
            # KiCAD schematics include library symbol definitions
            if hasattr(schematic, 'tree') and isinstance(schematic.tree, list):
                for item in schematic.tree:
                    if isinstance(item, list) and len(item) > 0:
                        if hasattr(item[0], 'value') and item[0].value() == 'lib_symbols':
                            # Found lib_symbols section
                            for lib_symbol in item[1:]:
                                if isinstance(lib_symbol, list) and len(lib_symbol) > 1:
                                    if hasattr(lib_symbol[0], 'value') and lib_symbol[0].value() == 'symbol':
                                        # Check if this is the symbol we're looking for
                                        for prop in lib_symbol[1:]:
                                            if isinstance(prop, str) and prop == lib_id:
                                                # Found the library symbol, extract pins
                                                pins = []
                                                # Recursively search for pin definitions
                                                def extract_pins(node, depth=0):
                                                    if depth > 10:  # Prevent infinite recursion
                                                        return
                                                    if isinstance(node, list):
                                                        for subnode in node:
                                                            if isinstance(subnode, list) and len(subnode) > 1:
                                                                if hasattr(subnode[0], 'value') and subnode[0].value() == 'pin':
                                                                    # Found a pin, extract number
                                                                    for pin_prop in subnode[1:]:
                                                                        if isinstance(pin_prop, str):
                                                                            pins.append(pin_prop)
                                                                            break
                                                            extract_pins(subnode, depth + 1)

                                                extract_pins(lib_symbol)
                                                if pins:
                                                    return pins

            # If we couldn't find pins, return empty list
            # The symbol might not have the library definition in the schematic yet
            return []
        except Exception as e:
            print(f"Warning: Could not extract pins from library symbol: {e}")
            return []

    @staticmethod
    def _create_pin_sexprs(pin_numbers: list):
        """Create pin S-expressions with UUIDs"""
        pin_exprs = []
        for pin_num in pin_numbers:
            pin_uuid = str(uuid.uuid4())
            pin_expr = [
                sexpdata.Symbol('pin'),
                str(pin_num),
                [sexpdata.Symbol('uuid'), pin_uuid]
            ]
            pin_exprs.append(pin_expr)
        return pin_exprs

    @staticmethod
    def _create_instances_sexpr(project_uuid: str, reference: str, unit: int = 1):
        """Create instances S-expression"""
        instances_expr = [
            sexpdata.Symbol('instances'),
            [
                sexpdata.Symbol('project'),
                "",
                [
                    sexpdata.Symbol('path'),
                    f"/{project_uuid}",
                    [sexpdata.Symbol('reference'), reference],
                    [sexpdata.Symbol('unit'), unit]
                ]
            ]
        ]
        return instances_expr

    @staticmethod
    def create_symbol_sexpr(schematic: Schematic, lib_id: str, reference: str, value: str,
                           x: float, y: float, rotation: int = 0, unit: int = 1,
                           footprint: str = "", datasheet: str = "",
                           exclude_from_sim: bool = False, in_bom: bool = True,
                           on_board: bool = True, dnp: bool = False,
                           fields_autoplaced: bool = True):
        """Create a complete symbol S-expression"""

        # Generate UUIDs
        symbol_uuid = str(uuid.uuid4())
        project_uuid = ComponentManager._get_project_uuid(schematic)

        # Get pins from library (if available)
        pins = ComponentManager._get_library_symbol_pins(schematic, lib_id)

        # Create properties
        # Reference and Value are visible and positioned above the symbol
        ref_offset_y = -5.08  # About 0.2 inches above
        val_offset_y = -2.54  # About 0.1 inches above

        properties = [
            ComponentManager._create_property_sexpr("Reference", reference, x, y + ref_offset_y, 0, hide=False),
            ComponentManager._create_property_sexpr("Value", value, x, y + val_offset_y, 0, hide=False),
            ComponentManager._create_property_sexpr("Footprint", footprint, x, y, 0, hide=True, justify="bottom" if footprint else None),
            ComponentManager._create_property_sexpr("Datasheet", datasheet if datasheet else "~", x, y, 0, hide=True),
        ]

        # Create pin expressions
        pin_exprs = ComponentManager._create_pin_sexprs(pins)

        # Create instances
        instances_expr = ComponentManager._create_instances_sexpr(project_uuid, reference, unit)

        # Build complete symbol expression
        symbol_expr = [
            sexpdata.Symbol('symbol'),
            [sexpdata.Symbol('lib_id'), lib_id],
            [sexpdata.Symbol('at'), x, y, rotation],
            [sexpdata.Symbol('unit'), unit],
            [sexpdata.Symbol('exclude_from_sim'), sexpdata.Symbol('yes' if exclude_from_sim else 'no')],
            [sexpdata.Symbol('in_bom'), sexpdata.Symbol('yes' if in_bom else 'no')],
            [sexpdata.Symbol('on_board'), sexpdata.Symbol('yes' if on_board else 'no')],
            [sexpdata.Symbol('dnp'), sexpdata.Symbol('yes' if dnp else 'no')],
            [sexpdata.Symbol('fields_autoplaced'), sexpdata.Symbol('yes' if fields_autoplaced else 'no')],
            [sexpdata.Symbol('uuid'), symbol_uuid]
        ]

        # Add properties
        symbol_expr.extend(properties)

        # Add pins
        symbol_expr.extend(pin_exprs)

        # Add instances
        symbol_expr.append(instances_expr)

        return symbol_expr

    @staticmethod
    def add_component(schematic: Schematic, component_def: dict):
        """Add a component to the schematic"""
        try:
            # Create a new symbol
            symbol = schematic.add_symbol(
                lib=component_def.get('library', 'Device'),
                name=component_def.get('type', 'R'), # Default to Resistor symbol 'R'
                reference=component_def.get('reference', 'R?'),
                at=[component_def.get('x', 0), component_def.get('y', 0)],
                unit=component_def.get('unit', 1),
                rotation=component_def.get('rotation', 0)
            )

            # Set properties
            if 'value' in component_def:
                symbol.property.Value.value = component_def['value']
            if 'footprint' in component_def:
                symbol.property.Footprint.value = component_def['footprint']
            if 'datasheet' in component_def:
                 symbol.property.Datasheet.value = component_def['datasheet']

            # Add additional properties
            for key, value in component_def.get('properties', {}).items():
                # Avoid overwriting standard properties unless explicitly intended
                if key not in ['Reference', 'Value', 'Footprint', 'Datasheet']:
                    symbol.property.append(key, value)

            print(f"Added component {symbol.reference} ({symbol.name}) to schematic.")
            return symbol
        except Exception as e:
            print(f"Error adding component: {e}")
            return None

    @staticmethod
    def remove_component(schematic: Schematic, component_ref: str):
        """Remove a component from the schematic by reference designator"""
        try:
            # kicad-skip doesn't have a direct remove_symbol method by reference.
            # We need to find the symbol and then remove it from the symbols list.
            symbol_to_remove = None
            for symbol in schematic.symbol:
                if symbol.reference == component_ref:
                    symbol_to_remove = symbol
                    break

            if symbol_to_remove:
                schematic.symbol.remove(symbol_to_remove)
                print(f"Removed component {component_ref} from schematic.")
                return True
            else:
                print(f"Component with reference {component_ref} not found.")
                return False
        except Exception as e:
            print(f"Error removing component {component_ref}: {e}")
            return False


    @staticmethod
    def update_component(schematic: Schematic, component_ref: str, new_properties: dict):
        """Update component properties by reference designator"""
        try:
            symbol_to_update = None
            for symbol in schematic.symbol:
                try:
                    ref = symbol.property.Reference.value if hasattr(symbol.property, 'Reference') else None
                    if ref == component_ref:
                        symbol_to_update = symbol
                        break
                except:
                    continue

            if symbol_to_update:
                for key, value in new_properties.items():
                    try:
                        # Access property using attribute notation
                        if hasattr(symbol_to_update.property, key):
                            prop = getattr(symbol_to_update.property, key)
                            prop.value = value
                        else:
                            # Property doesn't exist - skip for now
                            print(f"Warning: Property {key} not found on {component_ref}")
                    except Exception as e:
                        print(f"Error updating property {key}: {e}")
                print(f"Updated properties for component {component_ref}.")
                return True
            else:
                print(f"Component with reference {component_ref} not found.")
                return False
        except Exception as e:
            print(f"Error updating component {component_ref}: {e}")
            return False

    @staticmethod
    def get_component(schematic: Schematic, component_ref: str):
        """Get a component by reference designator"""
        for symbol in schematic.symbol:
            try:
                ref = symbol.property.Reference.value if hasattr(symbol.property, 'Reference') else None
                if ref == component_ref:
                    print(f"Found component with reference {component_ref}.")
                    return symbol
            except:
                continue
        print(f"Component with reference {component_ref} not found.")
        return None

    @staticmethod
    def search_components(schematic: Schematic, query: str):
        """Search for components matching criteria (basic implementation)"""
        # This is a basic search, could be expanded to use regex or more complex logic
        matching_components = []
        query_lower = query.lower()
        for symbol in schematic.symbol:
            if query_lower in symbol.reference.lower() or \
               query_lower in symbol.name.lower() or \
               (hasattr(symbol.property, 'Value') and query_lower in symbol.property.Value.value.lower()):
                matching_components.append(symbol)
        print(f"Found {len(matching_components)} components matching query '{query}'.")
        return matching_components

    @staticmethod
    def get_all_components(schematic: Schematic):
        """Get all components in schematic"""
        print(f"Retrieving all {len(schematic.symbol)} components.")
        return list(schematic.symbol)

    @staticmethod
    def save_schematic_with_tree(schematic: Schematic, file_path: str):
        """Save schematic by writing tree directly to file (bypass kicad-skip write)"""
        try:
            # schematic.tree already contains all elements INCLUDING the root 'kicad_sch' symbol
            # We need to wrap it: (kicad_sch version generator ... symbols ...)
            # tree[0] is 'kicad_sch' symbol, tree[1:] are the actual content elements

            # Build the complete S-expression: (kicad_sch <all elements except tree[0]>)
            kicad_sch_expr = [sexpdata.Symbol('kicad_sch')] + schematic.tree[1:]

            # Convert to S-expression string with pretty printing
            sexpr_str = sexpdata.dumps(kicad_sch_expr, pretty_print=True, indent_as='\t')

            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(sexpr_str)

            print(f"Saved schematic with tree to: {file_path}")
            return True
        except Exception as e:
            print(f"Error saving schematic with tree: {e}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def add_component_sexpr(schematic: Schematic, lib_id: str, reference: str, value: str,
                           x: float, y: float, rotation: int = 0, footprint: str = "",
                           datasheet: str = ""):
        """Add a component using S-expression at exact coordinates (Method 1)"""
        try:
            # Step 1: Ensure symbol definition is in lib_symbols
            if not ComponentManager._ensure_symbol_in_lib_symbols(schematic, lib_id):
                print(f"Warning: Could not add {lib_id} to lib_symbols, but continuing...")

            # Step 2: Create symbol instance S-expression
            symbol_expr = ComponentManager.create_symbol_sexpr(
                schematic, lib_id, reference, value, x, y, rotation,
                footprint=footprint, datasheet=datasheet
            )

            # Step 3: Find position to insert (before sheet_instances)
            if hasattr(schematic, 'tree') and isinstance(schematic.tree, list):
                insert_pos = len(schematic.tree)
                for i, item in enumerate(schematic.tree):
                    if isinstance(item, list) and len(item) > 0:
                        if hasattr(item[0], 'value') and item[0].value() == 'sheet_instances':
                            insert_pos = i
                            break

                schematic.tree.insert(insert_pos, symbol_expr)
                print(f"Added component {reference} ({lib_id}) at ({x}, {y}) to tree at position {insert_pos}")
                return True
            else:
                print("Error: Schematic tree not accessible")
                return False
        except Exception as e:
            print(f"Error adding component {reference}: {e}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def get_next_grid_position(schematic: Schematic, grid_x: int = 0, grid_y: int = 0, grid_size: float = 50.8):
        """Calculate next available grid position (Method 2 helper)"""
        # Get occupied positions
        occupied = set()
        for symbol in schematic.symbol:
            try:
                sx, sy = symbol.at[0], symbol.at[1]
                grid_sx = round(sx / grid_size)
                grid_sy = round(sy / grid_size)
                occupied.add((grid_sx, grid_sy))
            except:
                continue

        # Find next available position starting from grid_x, grid_y
        for row in range(grid_y, grid_y + 20):
            for col in range(grid_x, grid_x + 20):
                if (col, row) not in occupied:
                    return (col * grid_size, row * grid_size)

        # Fallback to original position if all occupied (unlikely)
        return (grid_x * grid_size, grid_y * grid_size)

    @staticmethod
    def add_component_auto(schematic: Schematic, lib_id: str, reference: str, value: str,
                          grid_x: int = 0, grid_y: int = 0, grid_size: float = 50.8,
                          rotation: int = 0, footprint: str = "", datasheet: str = ""):
        """Add a component with automatic grid-based positioning (Method 2)"""
        try:
            # Calculate position
            x, y = ComponentManager.get_next_grid_position(schematic, grid_x, grid_y, grid_size)

            # Add component at calculated position
            return ComponentManager.add_component_sexpr(
                schematic, lib_id, reference, value, x, y, rotation, footprint, datasheet
            )
        except Exception as e:
            print(f"Error adding component {reference} with auto positioning: {e}")
            return False

    @staticmethod
    def calculate_relative_position(schematic: Schematic, anchor_ref: str,
                                   direction: str = "right", distance: float = 25.4):
        """Calculate position relative to another component (Method 3 helper)"""
        # Find anchor component
        anchor_symbol = ComponentManager.get_component(schematic, anchor_ref)
        if not anchor_symbol:
            print(f"Anchor component {anchor_ref} not found")
            return None

        # Get anchor position
        try:
            anchor_x = anchor_symbol.at[0]
            anchor_y = anchor_symbol.at[1]
        except:
            print(f"Could not get position of anchor component {anchor_ref}")
            return None

        # Calculate offset based on direction
        offsets = {
            'right': (distance, 0),
            'left': (-distance, 0),
            'below': (0, distance),
            'above': (0, -distance),
            'below-right': (distance, distance),
            'below-left': (-distance, distance),
            'above-right': (distance, -distance),
            'above-left': (-distance, -distance)
        }

        dx, dy = offsets.get(direction, (distance, 0))
        return (anchor_x + dx, anchor_y + dy)

    @staticmethod
    def add_component_relative(schematic: Schematic, lib_id: str, reference: str, value: str,
                              anchor_ref: str, direction: str = "right", distance: float = 25.4,
                              rotation: int = 0, footprint: str = "", datasheet: str = ""):
        """Add a component relative to another component (Method 3)"""
        try:
            # Calculate position
            position = ComponentManager.calculate_relative_position(schematic, anchor_ref, direction, distance)
            if position is None:
                return False

            x, y = position

            # Add component at calculated position
            return ComponentManager.add_component_sexpr(
                schematic, lib_id, reference, value, x, y, rotation, footprint, datasheet
            )
        except Exception as e:
            print(f"Error adding component {reference} relative to {anchor_ref}: {e}")
            return False

    @staticmethod
    def add_component_group(schematic: Schematic, components: list, start_x: float = 100,
                          start_y: float = 100, spacing: float = 25.4, columns: int = 5):
        """Add multiple components in a group layout (Method 4)

        Args:
            components: List of dicts with keys: lib_id, reference, value, footprint (optional), datasheet (optional)
            start_x: Starting X coordinate
            start_y: Starting Y coordinate
            spacing: Distance between components
            columns: Number of columns before wrapping to next row
        """
        try:
            added_count = 0
            for i, comp in enumerate(components):
                # Calculate position in grid
                col = i % columns
                row = i // columns
                x = start_x + col * spacing
                y = start_y + row * spacing

                # Add component
                success = ComponentManager.add_component_sexpr(
                    schematic,
                    comp.get('lib_id'),
                    comp.get('reference'),
                    comp.get('value'),
                    x, y, 0,
                    comp.get('footprint', ''),
                    comp.get('datasheet', '')
                )

                if success:
                    added_count += 1

            print(f"Added {added_count}/{len(components)} components in group")
            return added_count == len(components)
        except Exception as e:
            print(f"Error adding component group: {e}")
            return False

if __name__ == '__main__':
    # Example Usage (for testing)
    from schematic import SchematicManager # Assuming schematic.py is in the same directory

    # Create a new schematic
    test_sch = SchematicManager.create_schematic("ComponentTestSchematic")

    # Add components
    comp1_def = {"type": "R", "reference": "R1", "value": "10k", "x": 100, "y": 100}
    comp2_def = {"type": "C", "reference": "C1", "value": "0.1uF", "x": 200, "y": 100, "library": "Device"}
    comp3_def = {"type": "LED", "reference": "D1", "x": 300, "y": 100, "library": "Device", "properties": {"Color": "Red"}}

    comp1 = ComponentManager.add_component(test_sch, comp1_def)
    comp2 = ComponentManager.add_component(test_sch, comp2_def)
    comp3 = ComponentManager.add_component(test_sch, comp3_def)

    # Get a component
    retrieved_comp = ComponentManager.get_component(test_sch, "C1")
    if retrieved_comp:
        print(f"Retrieved component: {retrieved_comp.reference} ({retrieved_comp.value})")

    # Update a component
    ComponentManager.update_component(test_sch, "R1", {"value": "20k", "Tolerance": "5%"})

    # Search components
    matching_comps = ComponentManager.search_components(test_sch, "100") # Search by position
    print(f"Search results for '100': {[c.reference for c in matching_comps]}")

    # Get all components
    all_comps = ComponentManager.get_all_components(test_sch)
    print(f"All components: {[c.reference for c in all_comps]}")

    # Remove a component
    ComponentManager.remove_component(test_sch, "D1")
    all_comps_after_remove = ComponentManager.get_all_components(test_sch)
    print(f"Components after removing D1: {[c.reference for c in all_comps_after_remove]}")

    # Save the schematic (optional)
    # SchematicManager.save_schematic(test_sch, "component_test.kicad_sch")

    # Clean up (if saved)
    # if os.path.exists("component_test.kicad_sch"):
    #     os.remove("component_test.kicad_sch")
    #     print("Cleaned up component_test.kicad_sch")
