#!/usr/bin/env python3
"""
KiCAD Python Interface Script for Model Context Protocol

This script handles communication between the MCP TypeScript server
and KiCAD's Python API (pcbnew). It receives commands via stdin as
JSON and returns responses via stdout also as JSON.
"""

import sys
import json
import traceback
import logging
import os
from typing import Dict, Any, Optional

# Import tool schemas and resource definitions
from schemas.tool_schemas import TOOL_SCHEMAS
from resources.resource_definitions import RESOURCE_DEFINITIONS, handle_resource_read

# Configure logging
log_dir = os.path.join(os.path.expanduser('~'), '.kicad-mcp', 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'kicad_interface.log')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger('kicad_interface')

# Log Python environment details
logger.info(f"Python version: {sys.version}")
logger.info(f"Python executable: {sys.executable}")
logger.info(f"Platform: {sys.platform}")
logger.info(f"Working directory: {os.getcwd()}")

# Windows-specific diagnostics
if sys.platform == 'win32':
    logger.info("=== Windows Environment Diagnostics ===")
    logger.info(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'NOT SET')}")
    logger.info(f"PATH: {os.environ.get('PATH', 'NOT SET')[:200]}...")  # Truncate PATH

    # Check for common KiCAD installations
    common_kicad_paths = [
        r"C:\Program Files\KiCad",
        r"C:\Program Files (x86)\KiCad"
    ]

    found_kicad = False
    for base_path in common_kicad_paths:
        if os.path.exists(base_path):
            logger.info(f"Found KiCAD installation at: {base_path}")
            # List versions
            try:
                versions = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
                logger.info(f"  Versions found: {', '.join(versions)}")
                for version in versions:
                    python_path = os.path.join(base_path, version, 'lib', 'python3', 'dist-packages')
                    if os.path.exists(python_path):
                        logger.info(f"  ✓ Python path exists: {python_path}")
                        found_kicad = True
                    else:
                        logger.warning(f"  ✗ Python path missing: {python_path}")
            except Exception as e:
                logger.warning(f"  Could not list versions: {e}")

    if not found_kicad:
        logger.warning("No KiCAD installations found in standard locations!")
        logger.warning("Please ensure KiCAD 9.0+ is installed from https://www.kicad.org/download/windows/")

    logger.info("========================================")

# Add utils directory to path for imports
utils_dir = os.path.join(os.path.dirname(__file__))
if utils_dir not in sys.path:
    sys.path.insert(0, utils_dir)

# Import platform helper and add KiCAD paths
from utils.platform_helper import PlatformHelper
from utils.kicad_process import check_and_launch_kicad, KiCADProcessManager

logger.info(f"Detecting KiCAD Python paths for {PlatformHelper.get_platform_name()}...")
paths_added = PlatformHelper.add_kicad_to_python_path()

if paths_added:
    logger.info("Successfully added KiCAD Python paths to sys.path")
else:
    logger.warning("No KiCAD Python paths found - attempting to import pcbnew from system path")

logger.info(f"Current Python path: {sys.path}")

# Check if auto-launch is enabled
AUTO_LAUNCH_KICAD = os.environ.get("KICAD_AUTO_LAUNCH", "false").lower() == "true"
if AUTO_LAUNCH_KICAD:
    logger.info("KiCAD auto-launch enabled")

# Import KiCAD's Python API
try:
    logger.info("Attempting to import pcbnew module...")
    import pcbnew  # type: ignore
    logger.info(f"Successfully imported pcbnew module from: {pcbnew.__file__}")
    logger.info(f"pcbnew version: {pcbnew.GetBuildVersion()}")
except ImportError as e:
    logger.error(f"Failed to import pcbnew module: {e}")
    logger.error(f"Current sys.path: {sys.path}")

    # Platform-specific help message
    help_message = ""
    if sys.platform == 'win32':
        help_message = """
Windows Troubleshooting:
1. Verify KiCAD is installed: C:\\Program Files\\KiCad\\9.0
2. Check PYTHONPATH environment variable points to:
   C:\\Program Files\\KiCad\\9.0\\lib\\python3\\dist-packages
3. Test with: "C:\\Program Files\\KiCad\\9.0\\bin\\python.exe" -c "import pcbnew"
4. Log file location: %USERPROFILE%\\.kicad-mcp\\logs\\kicad_interface.log
5. Run setup-windows.ps1 for automatic configuration
"""
    elif sys.platform == 'darwin':
        help_message = """
macOS Troubleshooting:
1. Verify KiCAD is installed: /Applications/KiCad/KiCad.app
2. Check PYTHONPATH points to KiCAD's Python packages
3. Run: python3 -c "import pcbnew" to test
"""
    else:  # Linux
        help_message = """
Linux Troubleshooting:
1. Verify KiCAD is installed: apt list --installed | grep kicad
2. Check: /usr/lib/kicad/lib/python3/dist-packages exists
3. Test: python3 -c "import pcbnew"
"""

    logger.error(help_message)

    error_response = {
        "success": False,
        "message": "Failed to import pcbnew module - KiCAD Python API not found",
        "errorDetails": f"Error: {str(e)}\n\n{help_message}\n\nPython sys.path:\n{chr(10).join(sys.path)}"
    }
    print(json.dumps(error_response))
    sys.exit(1)
except Exception as e:
    logger.error(f"Unexpected error importing pcbnew: {e}")
    logger.error(traceback.format_exc())
    error_response = {
        "success": False,
        "message": "Error importing pcbnew module",
        "errorDetails": str(e)
    }
    print(json.dumps(error_response))
    sys.exit(1)

# Import command handlers
try:
    logger.info("Importing command handlers...")
    from commands.project import ProjectCommands
    from commands.board import BoardCommands
    from commands.component import ComponentCommands
    from commands.routing import RoutingCommands
    from commands.design_rules import DesignRuleCommands
    from commands.export import ExportCommands
    from commands.schematic import SchematicManager
    from commands.component_schematic import ComponentManager
    from commands.connection_schematic import ConnectionManager
    from commands.library_schematic import LibraryManager as SchematicLibraryManager
    from commands.library import LibraryManager as FootprintLibraryManager, LibraryCommands
    from skip import Schematic  # Import Schematic class for wire operations
    logger.info("Successfully imported all command handlers")
except ImportError as e:
    logger.error(f"Failed to import command handlers: {e}")
    error_response = {
        "success": False,
        "message": "Failed to import command handlers",
        "errorDetails": str(e)
    }
    print(json.dumps(error_response))
    sys.exit(1)

class KiCADInterface:
    """Main interface class to handle KiCAD operations"""

    def __init__(self):
        """Initialize the interface and command handlers"""
        self.board = None
        self.project_filename = None

        logger.info("Initializing command handlers...")

        # Initialize footprint library manager
        self.footprint_library = FootprintLibraryManager()

        # Initialize command handlers
        self.project_commands = ProjectCommands(self.board)
        self.board_commands = BoardCommands(self.board)
        self.component_commands = ComponentCommands(self.board, self.footprint_library)
        self.routing_commands = RoutingCommands(self.board)
        self.design_rule_commands = DesignRuleCommands(self.board)
        self.export_commands = ExportCommands(self.board)
        self.library_commands = LibraryCommands(self.footprint_library)

        # Schematic-related classes don't need board reference
        # as they operate directly on schematic files
        
        # Command routing dictionary
        self.command_routes = {
            # Project commands
            "create_project": self.project_commands.create_project,
            "open_project": self.project_commands.open_project,
            "save_project": self.project_commands.save_project,
            "get_project_info": self.project_commands.get_project_info,
            
            # Board commands
            "set_board_size": self.board_commands.set_board_size,
            "add_layer": self.board_commands.add_layer,
            "set_active_layer": self.board_commands.set_active_layer,
            "get_board_info": self.board_commands.get_board_info,
            "get_layer_list": self.board_commands.get_layer_list,
            "get_board_2d_view": self.board_commands.get_board_2d_view,
            "add_board_outline": self.board_commands.add_board_outline,
            "add_mounting_hole": self.board_commands.add_mounting_hole,
            "add_text": self.board_commands.add_text,
            "add_board_text": self.board_commands.add_text,  # Alias for TypeScript tool
            
            # Component commands
            "place_component": self.component_commands.place_component,
            "move_component": self.component_commands.move_component,
            "rotate_component": self.component_commands.rotate_component,
            "delete_component": self.component_commands.delete_component,
            "edit_component": self.component_commands.edit_component,
            "get_component_properties": self.component_commands.get_component_properties,
            "get_component_list": self.component_commands.get_component_list,
            "place_component_array": self.component_commands.place_component_array,
            "align_components": self.component_commands.align_components,
            "duplicate_component": self.component_commands.duplicate_component,
            
            # Routing commands
            "add_net": self.routing_commands.add_net,
            "route_trace": self.routing_commands.route_trace,
            "add_via": self.routing_commands.add_via,
            "delete_trace": self.routing_commands.delete_trace,
            "get_nets_list": self.routing_commands.get_nets_list,
            "create_netclass": self.routing_commands.create_netclass,
            "add_copper_pour": self.routing_commands.add_copper_pour,
            "route_differential_pair": self.routing_commands.route_differential_pair,
            
            # Design rule commands
            "set_design_rules": self.design_rule_commands.set_design_rules,
            "get_design_rules": self.design_rule_commands.get_design_rules,
            "run_drc": self.design_rule_commands.run_drc,
            "get_drc_violations": self.design_rule_commands.get_drc_violations,
            
            # Export commands
            "export_gerber": self.export_commands.export_gerber,
            "export_pdf": self.export_commands.export_pdf,
            "export_svg": self.export_commands.export_svg,
            "export_3d": self.export_commands.export_3d,
            "export_bom": self.export_commands.export_bom,

            # Library commands (footprint management)
            "list_libraries": self.library_commands.list_libraries,
            "search_footprints": self.library_commands.search_footprints,
            "list_library_footprints": self.library_commands.list_library_footprints,
            "get_footprint_info": self.library_commands.get_footprint_info,

            # Schematic commands
            "create_schematic": self._handle_create_schematic,
            "load_schematic": self._handle_load_schematic,
            "get_all_symbols": self._handle_get_all_symbols,
            "get_symbol_properties": self._handle_get_symbol_properties,
            "update_symbol_property": self._handle_update_symbol_property,
            "add_schematic_component": self._handle_add_schematic_component,
            "add_schematic_wire": self._handle_add_schematic_wire,
            "add_schematic_label": self._handle_add_schematic_label,
            "list_schematic_libraries": self._handle_list_schematic_libraries,
            "export_schematic_pdf": self._handle_export_schematic_pdf,

            # Symbol addition commands (S-expression based)
            "add_symbol": self._handle_add_symbol,
            "add_symbol_auto": self._handle_add_symbol_auto,
            "add_symbol_relative": self._handle_add_symbol_relative,
            "add_symbol_group": self._handle_add_symbol_group,

            # Symbol deletion commands
            "delete_symbol": self._handle_delete_symbol,
            "delete_symbols": self._handle_delete_symbols,
            "delete_all_wires": self._handle_delete_all_wires,

            # Wire and label commands
            "add_wire": self._handle_add_wire,
            "add_label": self._handle_add_label,

            # High-level circuit creation
            "create_circuit": self._handle_create_circuit,

            # UI/Process management commands
            "check_kicad_ui": self._handle_check_kicad_ui,
            "launch_kicad_ui": self._handle_launch_kicad_ui
        }
        
        logger.info("KiCAD interface initialized")

    def handle_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Route command to appropriate handler"""
        logger.info(f"Handling command: {command}")
        logger.debug(f"Command parameters: {params}")
        
        try:
            # Get the handler for the command
            handler = self.command_routes.get(command)
            
            if handler:
                # Execute the command
                result = handler(params)
                logger.debug(f"Command result: {result}")
                
                # Update board reference if command was successful
                if result.get("success", False):
                    if command == "create_project" or command == "open_project":
                        logger.info("Updating board reference...")
                        # Get board from the project commands handler
                        self.board = self.project_commands.board
                        self._update_command_handlers()
                
                return result
            else:
                logger.error(f"Unknown command: {command}")
                return {
                    "success": False,
                    "message": f"Unknown command: {command}",
                    "errorDetails": "The specified command is not supported"
                }
                
        except Exception as e:
            # Get the full traceback
            traceback_str = traceback.format_exc()
            logger.error(f"Error handling command {command}: {str(e)}\n{traceback_str}")
            return {
                "success": False,
                "message": f"Error handling command: {command}",
                "errorDetails": f"{str(e)}\n{traceback_str}"
            }

    def _update_command_handlers(self):
        """Update board reference in all command handlers"""
        logger.debug("Updating board reference in command handlers")
        self.project_commands.board = self.board
        self.board_commands.board = self.board
        self.component_commands.board = self.board
        self.routing_commands.board = self.board
        self.design_rule_commands.board = self.board
        self.export_commands.board = self.board
        
    # Schematic command handlers
    def _handle_create_schematic(self, params):
        """Create a new schematic"""
        logger.info("Creating schematic")
        try:
            project_name = params.get("projectName")
            path = params.get("path", ".")
            metadata = params.get("metadata", {})
            
            if not project_name:
                return {"success": False, "message": "Project name is required"}
            
            schematic = SchematicManager.create_schematic(project_name, metadata)
            file_path = f"{path}/{project_name}.kicad_sch"
            success = SchematicManager.save_schematic(schematic, file_path)
            
            return {"success": success, "file_path": file_path}
        except Exception as e:
            logger.error(f"Error creating schematic: {str(e)}")
            return {"success": False, "message": str(e)}
    
    def _handle_load_schematic(self, params):
        """Load an existing schematic"""
        logger.info("Loading schematic")
        try:
            file_path = params.get("file_path") or params.get("filename")

            if not file_path:
                return {"success": False, "message": "file_path is required"}

            schematic = SchematicManager.load_schematic(file_path)
            success = schematic is not None

            if success:
                metadata_raw = SchematicManager.get_schematic_metadata(schematic)
                # Convert ParsedValue objects to strings
                metadata = {}
                for key, value in metadata_raw.items():
                    metadata[key] = str(value)
                return {"success": success, "metadata": metadata, "file_path": file_path}
            else:
                return {"success": False, "message": "Failed to load schematic"}
        except Exception as e:
            logger.error(f"Error loading schematic: {str(e)}")
            return {"success": False, "message": str(e)}

    def _handle_get_all_symbols(self, params):
        """Get all symbols from a schematic"""
        logger.info("Getting all symbols from schematic")
        try:
            file_path = params.get("file_path")

            if not file_path:
                return {"success": False, "message": "file_path is required"}

            schematic = SchematicManager.load_schematic(file_path)
            if not schematic:
                return {"success": False, "message": "Failed to load schematic"}

            symbols = ComponentManager.get_all_components(schematic)

            # Convert symbols to dict format
            symbols_data = []
            for sym in symbols:
                try:
                    sym_data = {
                        "reference": sym.property.Reference.value if hasattr(sym.property, 'Reference') else "?",
                        "value": sym.property.Value.value if hasattr(sym.property, 'Value') else "",
                        "lib_id": sym.lib_id.value if hasattr(sym, 'lib_id') else "",
                        "footprint": sym.property.Footprint.value if hasattr(sym.property, 'Footprint') else "",
                        "position": {
                            "x": sym.at[0] if hasattr(sym, 'at') and len(sym.at) > 0 else 0,
                            "y": sym.at[1] if hasattr(sym, 'at') and len(sym.at) > 1 else 0,
                            "rotation": sym.at[2] if hasattr(sym, 'at') and len(sym.at) > 2 else 0
                        }
                    }
                    symbols_data.append(sym_data)
                except Exception as e:
                    logger.warning(f"Error processing symbol: {str(e)}")
                    continue

            return {
                "success": True,
                "count": len(symbols_data),
                "symbols": symbols_data
            }
        except Exception as e:
            logger.error(f"Error getting symbols: {str(e)}")
            return {"success": False, "message": str(e)}

    def _handle_get_symbol_properties(self, params):
        """Get properties of a specific symbol"""
        logger.info("Getting symbol properties")
        try:
            file_path = params.get("file_path")
            reference = params.get("reference")

            if not file_path:
                return {"success": False, "message": "file_path is required"}
            if not reference:
                return {"success": False, "message": "reference is required"}

            schematic = SchematicManager.load_schematic(file_path)
            if not schematic:
                return {"success": False, "message": "Failed to load schematic"}

            symbol = ComponentManager.get_component(schematic, reference)
            if not symbol:
                return {"success": False, "message": f"Symbol {reference} not found"}

            # Extract all properties
            properties = {}
            if hasattr(symbol, 'property'):
                prop_names = [p for p in dir(symbol.property) if not p.startswith('_')]
                for prop_name in prop_names:
                    try:
                        prop = getattr(symbol.property, prop_name)
                        if hasattr(prop, 'value'):
                            properties[prop_name] = prop.value
                    except:
                        pass

            return {
                "success": True,
                "reference": reference,
                "properties": properties,
                "lib_id": symbol.lib_id.value if hasattr(symbol, 'lib_id') else "",
                "position": {
                    "x": symbol.at[0] if hasattr(symbol, 'at') and len(symbol.at) > 0 else 0,
                    "y": symbol.at[1] if hasattr(symbol, 'at') and len(symbol.at) > 1 else 0,
                    "rotation": symbol.at[2] if hasattr(symbol, 'at') and len(symbol.at) > 2 else 0
                }
            }
        except Exception as e:
            logger.error(f"Error getting symbol properties: {str(e)}")
            return {"success": False, "message": str(e)}

    def _handle_update_symbol_property(self, params):
        """Update a property of a specific symbol"""
        logger.info("Updating symbol property")
        try:
            file_path = params.get("file_path")
            reference = params.get("reference")
            property_name = params.get("property")
            value = params.get("value")
            output_path = params.get("output_path")

            if not file_path:
                return {"success": False, "message": "file_path is required"}
            if not reference:
                return {"success": False, "message": "reference is required"}
            if not property_name:
                return {"success": False, "message": "property name is required"}
            if value is None:
                return {"success": False, "message": "value is required"}

            schematic = SchematicManager.load_schematic(file_path)
            if not schematic:
                return {"success": False, "message": "Failed to load schematic"}

            # Update the property
            success = ComponentManager.update_component(schematic, reference, {property_name: value})

            if success:
                # Save the schematic
                save_path = output_path if output_path else file_path
                save_success = ComponentManager.save_schematic_with_tree(schematic, save_path)

                if save_success:
                    return {
                        "success": True,
                        "message": f"Updated {property_name} of {reference} to {value}",
                        "file_path": save_path
                    }
                else:
                    return {"success": False, "message": "Failed to save schematic"}
            else:
                return {"success": False, "message": f"Failed to update {reference}"}
        except Exception as e:
            logger.error(f"Error updating symbol property: {str(e)}")
            return {"success": False, "message": str(e)}

    def _handle_add_schematic_component(self, params):
        """Add a component to a schematic"""
        logger.info("Adding component to schematic")
        try:
            schematic_path = params.get("schematicPath")
            component = params.get("component", {})
            
            if not schematic_path:
                return {"success": False, "message": "Schematic path is required"}
            if not component:
                return {"success": False, "message": "Component definition is required"}
            
            schematic = SchematicManager.load_schematic(schematic_path)
            if not schematic:
                return {"success": False, "message": "Failed to load schematic"}
            
            component_obj = ComponentManager.add_component(schematic, component)
            success = component_obj is not None
            
            if success:
                SchematicManager.save_schematic(schematic, schematic_path)
                return {"success": True}
            else:
                return {"success": False, "message": "Failed to add component"}
        except Exception as e:
            logger.error(f"Error adding component to schematic: {str(e)}")
            return {"success": False, "message": str(e)}
    
    def _handle_add_schematic_wire(self, params):
        """Add a wire to a schematic"""
        logger.info("Adding wire to schematic")
        try:
            # Support both naming conventions
            schematic_path = params.get("file_path") or params.get("schematicPath")
            start_point = params.get("start_point") or params.get("startPoint")
            end_point = params.get("end_point") or params.get("endPoint")

            if not schematic_path:
                return {"success": False, "message": "Schematic path is required"}
            if not start_point or not end_point:
                return {"success": False, "message": "Start and end points are required"}

            logger.debug(f"Will read {schematic_path}")
            schematic = Schematic(schematic_path)
            if not schematic:
                return {"success": False, "message": "Failed to load schematic"}

            wire = ConnectionManager.add_wire(schematic, start_point, end_point)
            success = wire is not None

            if success:
                # Save using tree-based save (same as component addition)
                if ComponentManager.save_schematic_with_tree(schematic, schematic_path):
                    logger.info(f"Saved wire to {schematic_path}")
                    return {"success": True, "message": f"Added wire from {start_point} to {end_point}", "file_path": schematic_path}
                else:
                    return {"success": False, "message": "Failed to save schematic"}
            else:
                return {"success": False, "message": "Failed to add wire"}
        except Exception as e:
            logger.error(f"Error adding wire to schematic: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e)}
    
    def _handle_add_schematic_label(self, params):
        """Add a label to a schematic"""
        logger.info("Adding label to schematic")
        try:
            # Support both naming conventions
            schematic_path = params.get("file_path") or params.get("schematicPath")
            text = params.get("text")
            x = params.get("x")
            y = params.get("y")
            label_type = params.get("label_type", "label")  # default to "label"

            if not schematic_path:
                return {"success": False, "message": "Schematic path is required"}
            if not text:
                return {"success": False, "message": "Label text is required"}
            if x is None or y is None:
                return {"success": False, "message": "X and Y coordinates are required"}

            logger.debug(f"Will read {schematic_path}")
            schematic = Schematic(schematic_path)
            if not schematic:
                return {"success": False, "message": "Failed to load schematic"}

            label = ConnectionManager.add_label(schematic, text, x, y, label_type)
            success = label is not None

            if success:
                # Save using tree-based save (same as component addition)
                if ComponentManager.save_schematic_with_tree(schematic, schematic_path):
                    logger.info(f"Saved label to {schematic_path}")
                    return {"success": True, "message": f"Added {label_type} '{text}' at ({x}, {y})", "file_path": schematic_path}
                else:
                    return {"success": False, "message": "Failed to save schematic"}
            else:
                return {"success": False, "message": "Failed to add label"}
        except Exception as e:
            logger.error(f"Error adding label to schematic: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e)}

    def _handle_list_schematic_libraries(self, params):
        """List available symbol libraries"""
        logger.info("Listing schematic libraries")
        try:
            search_paths = params.get("searchPaths")

            libraries = LibraryManager.list_available_libraries(search_paths)
            return {"success": True, "libraries": libraries}
        except Exception as e:
            logger.error(f"Error listing schematic libraries: {str(e)}")
            return {"success": False, "message": str(e)}
    
    def _handle_export_schematic_pdf(self, params):
        """Export schematic to PDF"""
        logger.info("Exporting schematic to PDF")
        try:
            schematic_path = params.get("schematicPath")
            output_path = params.get("outputPath")

            if not schematic_path:
                return {"success": False, "message": "Schematic path is required"}
            if not output_path:
                return {"success": False, "message": "Output path is required"}

            import subprocess
            result = subprocess.run(
                ["kicad-cli", "sch", "export", "pdf", "--output", output_path, schematic_path],
                capture_output=True,
                text=True
            )

            success = result.returncode == 0
            message = result.stderr if not success else ""

            return {"success": success, "message": message}
        except Exception as e:
            logger.error(f"Error exporting schematic to PDF: {str(e)}")
            return {"success": False, "message": str(e)}

    def _handle_add_symbol(self, params):
        """Add symbol at exact coordinates (Method 1)"""
        logger.info("Adding symbol with exact coordinates")
        try:
            file_path = params.get("file_path")
            lib_id = params.get("lib_id")
            reference = params.get("reference")
            value = params.get("value")
            x = params.get("x")
            y = params.get("y")
            rotation = params.get("rotation", 0)
            footprint = params.get("footprint", "")
            datasheet = params.get("datasheet", "")
            output_path = params.get("output_path")
            auto_rotate = params.get("auto_rotate", False)
            desired_orientation = params.get("desired_orientation")

            if not file_path:
                return {"success": False, "message": "file_path is required"}
            if not lib_id:
                return {"success": False, "message": "lib_id is required"}
            if not reference:
                return {"success": False, "message": "reference is required"}
            if not value:
                return {"success": False, "message": "value is required"}
            if x is None:
                return {"success": False, "message": "x coordinate is required"}
            if y is None:
                return {"success": False, "message": "y coordinate is required"}

            # Load schematic
            from commands.schematic import SchematicManager
            from commands.component_schematic import ComponentManager

            schematic = SchematicManager.load_schematic(file_path)
            if not schematic:
                return {"success": False, "message": "Failed to load schematic"}

            # Add component with auto-rotation support
            success = ComponentManager.add_component_sexpr(
                schematic, lib_id, reference, value, x, y, rotation, footprint, datasheet,
                auto_rotate=auto_rotate, desired_orientation=desired_orientation
            )

            if success:
                # Save schematic using tree-based save
                save_path = output_path if output_path else file_path
                save_success = ComponentManager.save_schematic_with_tree(schematic, save_path)

                if save_success:
                    # Get final rotation from schematic
                    final_rotation = rotation  # Will be updated by auto_rotate logic
                    return {
                        "success": True,
                        "message": f"Added {reference} ({lib_id}) at ({x}, {y})",
                        "file_path": save_path,
                        "reference": reference,
                        "position": {"x": x, "y": y, "rotation": final_rotation},
                        "auto_rotate": auto_rotate,
                        "desired_orientation": desired_orientation
                    }
                else:
                    return {"success": False, "message": "Failed to save schematic"}
            else:
                return {"success": False, "message": f"Failed to add component {reference}"}
        except Exception as e:
            logger.error(f"Error adding symbol: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e)}

    def _handle_add_symbol_auto(self, params):
        """Add symbol with automatic grid positioning (Method 2)"""
        logger.info("Adding symbol with auto grid positioning")
        try:
            file_path = params.get("file_path")
            lib_id = params.get("lib_id")
            reference = params.get("reference")
            value = params.get("value")
            grid_x = params.get("grid_x", 0)
            grid_y = params.get("grid_y", 0)
            grid_size = params.get("grid_size", 50.8)
            rotation = params.get("rotation", 0)
            footprint = params.get("footprint", "")
            datasheet = params.get("datasheet", "")
            output_path = params.get("output_path")

            if not file_path:
                return {"success": False, "message": "file_path is required"}
            if not lib_id:
                return {"success": False, "message": "lib_id is required"}
            if not reference:
                return {"success": False, "message": "reference is required"}
            if not value:
                return {"success": False, "message": "value is required"}

            # Load schematic
            from commands.schematic import SchematicManager
            from commands.component_schematic import ComponentManager

            schematic = SchematicManager.load_schematic(file_path)
            if not schematic:
                return {"success": False, "message": "Failed to load schematic"}

            # Add component with auto positioning
            success = ComponentManager.add_component_auto(
                schematic, lib_id, reference, value, grid_x, grid_y, grid_size, rotation, footprint, datasheet
            )

            if success:
                # Get actual position
                added_symbol = ComponentManager.get_component(schematic, reference)
                actual_x = added_symbol.at[0] if added_symbol else 0
                actual_y = added_symbol.at[1] if added_symbol else 0

                # Save schematic
                save_path = output_path if output_path else file_path
                save_success = ComponentManager.save_schematic_with_tree(schematic, save_path)

                if save_success:
                    return {
                        "success": True,
                        "message": f"Added {reference} ({lib_id}) with auto positioning",
                        "file_path": save_path,
                        "reference": reference,
                        "position": {"x": actual_x, "y": actual_y, "rotation": rotation}
                    }
                else:
                    return {"success": False, "message": "Failed to save schematic"}
            else:
                return {"success": False, "message": f"Failed to add component {reference}"}
        except Exception as e:
            logger.error(f"Error adding symbol with auto positioning: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e)}

    def _handle_add_symbol_relative(self, params):
        """Add symbol relative to another component (Method 3)"""
        logger.info("Adding symbol with relative positioning")
        try:
            file_path = params.get("file_path")
            lib_id = params.get("lib_id")
            reference = params.get("reference")
            value = params.get("value")
            anchor_ref = params.get("anchor_ref")
            direction = params.get("direction", "right")
            distance = params.get("distance", 25.4)
            rotation = params.get("rotation", 0)
            footprint = params.get("footprint", "")
            datasheet = params.get("datasheet", "")
            output_path = params.get("output_path")

            if not file_path:
                return {"success": False, "message": "file_path is required"}
            if not lib_id:
                return {"success": False, "message": "lib_id is required"}
            if not reference:
                return {"success": False, "message": "reference is required"}
            if not value:
                return {"success": False, "message": "value is required"}
            if not anchor_ref:
                return {"success": False, "message": "anchor_ref is required"}

            # Load schematic
            from commands.schematic import SchematicManager
            from commands.component_schematic import ComponentManager

            schematic = SchematicManager.load_schematic(file_path)
            if not schematic:
                return {"success": False, "message": "Failed to load schematic"}

            # Add component with relative positioning
            success = ComponentManager.add_component_relative(
                schematic, lib_id, reference, value, anchor_ref, direction, distance, rotation, footprint, datasheet
            )

            if success:
                # Get actual position
                added_symbol = ComponentManager.get_component(schematic, reference)
                actual_x = added_symbol.at[0] if added_symbol else 0
                actual_y = added_symbol.at[1] if added_symbol else 0

                # Save schematic
                save_path = output_path if output_path else file_path
                save_success = ComponentManager.save_schematic_with_tree(schematic, save_path)

                if save_success:
                    return {
                        "success": True,
                        "message": f"Added {reference} ({lib_id}) {direction} of {anchor_ref}",
                        "file_path": save_path,
                        "reference": reference,
                        "position": {"x": actual_x, "y": actual_y, "rotation": rotation},
                        "relative_to": anchor_ref,
                        "direction": direction
                    }
                else:
                    return {"success": False, "message": "Failed to save schematic"}
            else:
                return {"success": False, "message": f"Failed to add component {reference}"}
        except Exception as e:
            logger.error(f"Error adding symbol with relative positioning: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e)}

    def _handle_add_symbol_group(self, params):
        """Add multiple symbols in a group layout (Method 4)"""
        logger.info("Adding symbol group")
        try:
            file_path = params.get("file_path")
            components = params.get("components")
            start_x = params.get("start_x", 100)
            start_y = params.get("start_y", 100)
            spacing = params.get("spacing", 25.4)
            columns = params.get("columns", 5)
            output_path = params.get("output_path")

            if not file_path:
                return {"success": False, "message": "file_path is required"}
            if not components or not isinstance(components, list):
                return {"success": False, "message": "components array is required"}

            # Load schematic
            from commands.schematic import SchematicManager
            from commands.component_schematic import ComponentManager

            schematic = SchematicManager.load_schematic(file_path)
            if not schematic:
                return {"success": False, "message": "Failed to load schematic"}

            # Add component group
            success = ComponentManager.add_component_group(
                schematic, components, start_x, start_y, spacing, columns
            )

            if success:
                # Save schematic using tree-based save
                save_path = output_path if output_path else file_path
                save_success = ComponentManager.save_schematic_with_tree(schematic, save_path)

                if save_success:
                    return {
                        "success": True,
                        "message": f"Added {len(components)} components in group",
                        "file_path": save_path,
                        "count": len(components),
                        "components": [c.get('reference') for c in components]
                    }
                else:
                    return {"success": False, "message": "Failed to save schematic"}
            else:
                return {"success": False, "message": "Failed to add component group"}
        except Exception as e:
            logger.error(f"Error adding symbol group: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e)}

    def _handle_delete_symbol(self, params):
        """Delete a single symbol from schematic"""
        logger.info("Deleting symbol from schematic")
        try:
            file_path = params.get("file_path")
            reference = params.get("reference")
            output_path = params.get("output_path")

            if not file_path:
                return {"success": False, "message": "file_path is required"}
            if not reference:
                return {"success": False, "message": "reference is required"}

            # Load schematic file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.split('\n')
            output_lines = []

            in_lib_symbols = False
            in_instance_symbol = False
            skip_current_block = False
            symbol_start_line = 0

            i = 0
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()

                # Detect lib_symbols block
                # New format: "lib_symbols" on its own line, old format: "(lib_symbols ..."
                if stripped.startswith('(lib_symbols') or stripped == 'lib_symbols':
                    in_lib_symbols = True
                    output_lines.append(line)
                    i += 1
                    continue

                # End of lib_symbols block (one closing paren at same indent level)
                if in_lib_symbols and stripped == ')':
                    in_lib_symbols = False
                    output_lines.append(line)
                    i += 1
                    continue

                # Keep all lib_symbols content
                if in_lib_symbols:
                    output_lines.append(line)
                    i += 1
                    continue

                # Detect instance symbol (outside lib_symbols)
                # KiCAD 9.0 format: "(" on one line, then "symbol" on next line
                # Old format: "(symbol ..." on single line
                if not in_lib_symbols and stripped == '(':
                    # Check if next line is 'symbol'
                    if i + 1 < len(lines) and lines[i + 1].strip() == 'symbol':
                        temp_lines = []
                        temp_i = i
                        paren_count = 0
                        symbol_reference = None
                        found_property = False
                        found_reference_key = False

                        # Read entire symbol block
                        while temp_i < len(lines):
                            temp_line = lines[temp_i]
                            temp_lines.append(temp_line)
                            temp_stripped = temp_line.strip()
                            paren_count += temp_line.count('(') - temp_line.count(')')

                            # Find reference - handle both old and new formats
                            # Old format: property "Reference" "R4" on single line
                            # New format: property on line 1, "Reference" on line 2, "R4" on line 3
                            if 'property "Reference"' in temp_line and symbol_reference is None:
                                parts = temp_line.split('"')
                                if len(parts) >= 4:
                                    symbol_reference = parts[3]
                            elif temp_stripped == 'property':
                                found_property = True
                            elif found_property and temp_stripped == '"Reference"':
                                found_reference_key = True
                            elif found_reference_key and temp_stripped.startswith('"') and temp_stripped.endswith('"'):
                                # Extract reference value from quoted string
                                symbol_reference = temp_stripped.strip('"')
                                found_property = False
                                found_reference_key = False

                            if paren_count == 0:
                                break
                            temp_i += 1

                        # Check if this is the symbol to delete
                        if symbol_reference == reference:
                            # Skip this symbol
                            i = temp_i + 1
                            continue
                        else:
                            # Keep this symbol
                            output_lines.extend(temp_lines)
                            i = temp_i + 1
                            continue
                elif not in_lib_symbols and stripped.startswith('(symbol'):
                    # Old format: "(symbol ..." on single line
                    temp_lines = []
                    temp_i = i
                    paren_count = 0
                    symbol_reference = None

                    # Read entire symbol block
                    while temp_i < len(lines):
                        temp_line = lines[temp_i]
                        temp_lines.append(temp_line)
                        paren_count += temp_line.count('(') - temp_line.count(')')

                        # Find reference
                        if 'property "Reference"' in temp_line and symbol_reference is None:
                            parts = temp_line.split('"')
                            if len(parts) >= 4:
                                symbol_reference = parts[3]

                        if paren_count == 0:
                            break
                        temp_i += 1

                    # Check if this is the symbol to delete
                    if symbol_reference == reference:
                        # Skip this symbol
                        i = temp_i + 1
                        continue
                    else:
                        # Keep this symbol
                        output_lines.extend(temp_lines)
                        i = temp_i + 1
                        continue

                # Keep all other lines
                output_lines.append(line)
                i += 1

            # Write output
            save_path = output_path if output_path else file_path
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(output_lines))

            return {
                "success": True,
                "message": f"Deleted symbol {reference}",
                "file_path": save_path,
                "reference": reference
            }
        except Exception as e:
            logger.error(f"Error deleting symbol: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e)}

    def _handle_delete_symbols(self, params):
        """Delete multiple symbols from schematic"""
        logger.info("Deleting multiple symbols from schematic")
        try:
            file_path = params.get("file_path")
            references = params.get("references")
            output_path = params.get("output_path")

            if not file_path:
                return {"success": False, "message": "file_path is required"}
            if not references or not isinstance(references, list):
                return {"success": False, "message": "references array is required"}

            # Load schematic file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.split('\n')
            output_lines = []

            in_lib_symbols = False
            deleted_count = 0

            i = 0
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()

                # Detect lib_symbols block
                # New format: "lib_symbols" on its own line, old format: "(lib_symbols ..."
                if stripped.startswith('(lib_symbols') or stripped == 'lib_symbols':
                    in_lib_symbols = True
                    output_lines.append(line)
                    i += 1
                    continue

                # End of lib_symbols block (one closing paren at same indent level)
                if in_lib_symbols and stripped == ')':
                    in_lib_symbols = False
                    output_lines.append(line)
                    i += 1
                    continue

                # Keep all lib_symbols content
                if in_lib_symbols:
                    output_lines.append(line)
                    i += 1
                    continue

                # Detect instance symbol (outside lib_symbols)
                # KiCAD 9.0 format: "(" on one line, then "symbol" on next line
                # Old format: "(symbol ..." on single line
                if not in_lib_symbols and stripped == '(':
                    # Check if next line is 'symbol'
                    if i + 1 < len(lines) and lines[i + 1].strip() == 'symbol':
                        temp_lines = []
                        temp_i = i
                        paren_count = 0
                        symbol_reference = None
                        found_property = False
                        found_reference_key = False

                        # Read entire symbol block
                        while temp_i < len(lines):
                            temp_line = lines[temp_i]
                            temp_lines.append(temp_line)
                            temp_stripped = temp_line.strip()
                            paren_count += temp_line.count('(') - temp_line.count(')')

                            # Find reference - handle both old and new formats
                            # Old format: property "Reference" "R4" on single line
                            # New format: property on line 1, "Reference" on line 2, "R4" on line 3
                            if 'property "Reference"' in temp_line and symbol_reference is None:
                                parts = temp_line.split('"')
                                if len(parts) >= 4:
                                    symbol_reference = parts[3]
                            elif temp_stripped == 'property':
                                found_property = True
                            elif found_property and temp_stripped == '"Reference"':
                                found_reference_key = True
                            elif found_reference_key and temp_stripped.startswith('"') and temp_stripped.endswith('"'):
                                # Extract reference value from quoted string
                                symbol_reference = temp_stripped.strip('"')
                                found_property = False
                                found_reference_key = False

                            if paren_count == 0:
                                break
                            temp_i += 1

                        # Check if this symbol should be deleted
                        if symbol_reference in references:
                            # Skip this symbol
                            deleted_count += 1
                            i = temp_i + 1
                            continue
                        else:
                            # Keep this symbol
                            output_lines.extend(temp_lines)
                            i = temp_i + 1
                            continue
                elif not in_lib_symbols and stripped.startswith('(symbol'):
                    # Old format: "(symbol ..." on single line
                    temp_lines = []
                    temp_i = i
                    paren_count = 0
                    symbol_reference = None

                    # Read entire symbol block
                    while temp_i < len(lines):
                        temp_line = lines[temp_i]
                        temp_lines.append(temp_line)
                        paren_count += temp_line.count('(') - temp_line.count(')')

                        # Find reference
                        if 'property "Reference"' in temp_line and symbol_reference is None:
                            parts = temp_line.split('"')
                            if len(parts) >= 4:
                                symbol_reference = parts[3]

                        if paren_count == 0:
                            break
                        temp_i += 1

                    # Check if this symbol should be deleted
                    if symbol_reference in references:
                        # Skip this symbol
                        deleted_count += 1
                        i = temp_i + 1
                        continue
                    else:
                        # Keep this symbol
                        output_lines.extend(temp_lines)
                        i = temp_i + 1
                        continue

                # Keep all other lines
                output_lines.append(line)
                i += 1

            # Write output
            save_path = output_path if output_path else file_path
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(output_lines))

            return {
                "success": True,
                "message": f"Deleted {deleted_count} symbols",
                "file_path": save_path,
                "deleted_count": deleted_count,
                "references": references
            }
        except Exception as e:
            logger.error(f"Error deleting symbols: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e)}

    def _handle_delete_all_wires(self, params):
        """Delete all wires, junctions, and labels from schematic"""
        logger.info("Deleting all wires from schematic")
        try:
            file_path = params.get("file_path")
            output_path = params.get("output_path")

            if not file_path:
                return {"success": False, "message": "file_path is required"}

            # Load schematic file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.split('\n')
            output_lines = []

            i = 0
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()

                # Skip wire, junction, and label blocks
                if stripped.startswith('(wire') or stripped.startswith('(junction') or stripped.startswith('(label'):
                    temp_i = i
                    paren_count = 0
                    while temp_i < len(lines):
                        temp_line = lines[temp_i]
                        paren_count += temp_line.count('(') - temp_line.count(')')
                        if paren_count == 0:
                            break
                        temp_i += 1
                    i = temp_i + 1
                    continue

                # Keep all other lines
                output_lines.append(line)
                i += 1

            # Write output
            save_path = output_path if output_path else file_path
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(output_lines))

            return {
                "success": True,
                "message": "Deleted all wires, junctions, and labels",
                "file_path": save_path
            }
        except Exception as e:
            logger.error(f"Error deleting wires: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e)}

    def _handle_add_wire(self, params):
        """Add wire connection to schematic"""
        logger.info("Adding wire to schematic")
        try:
            file_path = params.get("file_path")
            start_x = params.get("start_x")
            start_y = params.get("start_y")
            end_x = params.get("end_x")
            end_y = params.get("end_y")
            output_path = params.get("output_path")

            if not file_path:
                return {"success": False, "message": "file_path is required"}
            if start_x is None or start_y is None:
                return {"success": False, "message": "start_x and start_y are required"}
            if end_x is None or end_y is None:
                return {"success": False, "message": "end_x and end_y are required"}

            from commands.schematic import SchematicManager
            from commands.connection_schematic import ConnectionManager
            from commands.component_schematic import ComponentManager

            schematic = SchematicManager.load_schematic(file_path)
            if not schematic:
                return {"success": False, "message": "Failed to load schematic"}

            wire = ConnectionManager.add_wire(schematic, [start_x, start_y], [end_x, end_y])

            if wire:
                save_path = output_path if output_path else file_path
                save_success = ComponentManager.save_schematic_with_tree(schematic, save_path)

                if save_success:
                    return {
                        "success": True,
                        "message": f"Added wire from ({start_x}, {start_y}) to ({end_x}, {end_y})",
                        "file_path": save_path
                    }
                else:
                    return {"success": False, "message": "Failed to save schematic"}
            else:
                return {"success": False, "message": "Failed to add wire"}

        except Exception as e:
            logger.error(f"Error adding wire: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e)}

    def _handle_add_label(self, params):
        """Add label to schematic"""
        logger.info("Adding label to schematic")
        try:
            file_path = params.get("file_path")
            text = params.get("text")
            x = params.get("x")
            y = params.get("y")
            label_type = params.get("label_type", "label")
            output_path = params.get("output_path")

            if not file_path:
                return {"success": False, "message": "file_path is required"}
            if not text:
                return {"success": False, "message": "text is required"}
            if x is None or y is None:
                return {"success": False, "message": "x and y coordinates are required"}

            from commands.schematic import SchematicManager
            from commands.connection_schematic import ConnectionManager
            from commands.component_schematic import ComponentManager

            schematic = SchematicManager.load_schematic(file_path)
            if not schematic:
                return {"success": False, "message": "Failed to load schematic"}

            label = ConnectionManager.add_label(schematic, text, x, y, label_type)

            if label:
                save_path = output_path if output_path else file_path
                save_success = ComponentManager.save_schematic_with_tree(schematic, save_path)

                if save_success:
                    return {
                        "success": True,
                        "message": f"Added {label_type} '{text}' at ({x}, {y})",
                        "file_path": save_path,
                        "label_type": label_type
                    }
                else:
                    return {"success": False, "message": "Failed to save schematic"}
            else:
                return {"success": False, "message": "Failed to add label"}

        except Exception as e:
            logger.error(f"Error adding label: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e)}

    def _handle_create_circuit(self, params):
        """Create complete circuit (high-level function)"""
        logger.info("Creating circuit")
        try:
            file_path = params.get("file_path")
            circuit_type = params.get("circuit_type")
            parameters = params.get("parameters", {})
            output_path = params.get("output_path")

            if not file_path:
                return {"success": False, "message": "file_path is required"}
            if not circuit_type:
                return {"success": False, "message": "circuit_type is required"}

            from commands.schematic import SchematicManager
            from commands.connection_schematic import ConnectionManager
            from commands.component_schematic import ComponentManager

            schematic = SchematicManager.load_schematic(file_path)
            if not schematic:
                return {"success": False, "message": "Failed to load schematic"}

            # Route to specific circuit creation function
            if circuit_type == "voltage_divider":
                result = ConnectionManager.create_voltage_divider_circuit(schematic, parameters)
            else:
                return {
                    "success": False,
                    "message": f"Unknown circuit type: {circuit_type}",
                    "supported_types": ["voltage_divider"]
                }

            if result.get("success"):
                save_path = output_path if output_path else file_path
                save_success = ComponentManager.save_schematic_with_tree(schematic, save_path)

                if save_success:
                    result["file_path"] = save_path
                    result["message"] = f"Created {circuit_type} circuit successfully"
                    return result
                else:
                    return {"success": False, "message": "Failed to save schematic"}
            else:
                return result

        except Exception as e:
            logger.error(f"Error creating circuit: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e)}

    def _handle_check_kicad_ui(self, params):
        """Check if KiCAD UI is running"""
        logger.info("Checking if KiCAD UI is running")
        try:
            manager = KiCADProcessManager()
            is_running = manager.is_running()
            processes = manager.get_process_info() if is_running else []

            return {
                "success": True,
                "running": is_running,
                "processes": processes,
                "message": "KiCAD is running" if is_running else "KiCAD is not running"
            }
        except Exception as e:
            logger.error(f"Error checking KiCAD UI status: {str(e)}")
            return {"success": False, "message": str(e)}

    def _handle_launch_kicad_ui(self, params):
        """Launch KiCAD UI"""
        logger.info("Launching KiCAD UI")
        try:
            project_path = params.get("projectPath")
            auto_launch = params.get("autoLaunch", AUTO_LAUNCH_KICAD)

            # Convert project path to Path object if provided
            from pathlib import Path
            path_obj = Path(project_path) if project_path else None

            result = check_and_launch_kicad(path_obj, auto_launch)

            return {
                "success": True,
                **result
            }
        except Exception as e:
            logger.error(f"Error launching KiCAD UI: {str(e)}")
            return {"success": False, "message": str(e)}

def main():
    """Main entry point"""
    logger.info("Starting KiCAD interface...")
    interface = KiCADInterface()

    try:
        logger.info("Processing commands from stdin...")
        # Process commands from stdin
        for line in sys.stdin:
            try:
                # Parse command
                logger.debug(f"Received input: {line.strip()}")
                command_data = json.loads(line)

                # Check if this is JSON-RPC 2.0 format
                if 'jsonrpc' in command_data and command_data['jsonrpc'] == '2.0':
                    logger.info("Detected JSON-RPC 2.0 format message")
                    method = command_data.get('method')
                    params = command_data.get('params', {})
                    request_id = command_data.get('id')

                    # Handle MCP protocol methods
                    if method == 'initialize':
                        logger.info("Handling MCP initialize")
                        response = {
                            'jsonrpc': '2.0',
                            'id': request_id,
                            'result': {
                                'protocolVersion': '2025-06-18',
                                'capabilities': {
                                    'tools': {
                                        'listChanged': True
                                    },
                                    'resources': {
                                        'subscribe': False,
                                        'listChanged': True
                                    }
                                },
                                'serverInfo': {
                                    'name': 'kicad-mcp-server',
                                    'title': 'KiCAD PCB Design Assistant',
                                    'version': '2.1.0-alpha'
                                },
                                'instructions': 'AI-assisted PCB design with KiCAD. Use tools to create projects, design boards, place components, route traces, and export manufacturing files.'
                            }
                        }
                    elif method == 'tools/list':
                        logger.info("Handling MCP tools/list")
                        # Return list of available tools with proper schemas
                        tools = []
                        for cmd_name in interface.command_routes.keys():
                            # Get schema from TOOL_SCHEMAS if available
                            if cmd_name in TOOL_SCHEMAS:
                                tool_def = TOOL_SCHEMAS[cmd_name].copy()
                                tools.append(tool_def)
                            else:
                                # Fallback for tools without schemas
                                logger.warning(f"No schema defined for tool: {cmd_name}")
                                tools.append({
                                    'name': cmd_name,
                                    'description': f'KiCAD command: {cmd_name}',
                                    'inputSchema': {
                                        'type': 'object',
                                        'properties': {}
                                    }
                                })

                        logger.info(f"Returning {len(tools)} tools")
                        response = {
                            'jsonrpc': '2.0',
                            'id': request_id,
                            'result': {
                                'tools': tools
                            }
                        }
                    elif method == 'tools/call':
                        logger.info("Handling MCP tools/call")
                        tool_name = params.get('name')
                        tool_params = params.get('arguments', {})

                        # Execute the command
                        result = interface.handle_command(tool_name, tool_params)

                        response = {
                            'jsonrpc': '2.0',
                            'id': request_id,
                            'result': {
                                'content': [
                                    {
                                        'type': 'text',
                                        'text': json.dumps(result)
                                    }
                                ]
                            }
                        }
                    elif method == 'resources/list':
                        logger.info("Handling MCP resources/list")
                        # Return list of available resources
                        response = {
                            'jsonrpc': '2.0',
                            'id': request_id,
                            'result': {
                                'resources': RESOURCE_DEFINITIONS
                            }
                        }
                    elif method == 'resources/read':
                        logger.info("Handling MCP resources/read")
                        resource_uri = params.get('uri')

                        if not resource_uri:
                            response = {
                                'jsonrpc': '2.0',
                                'id': request_id,
                                'error': {
                                    'code': -32602,
                                    'message': 'Missing required parameter: uri'
                                }
                            }
                        else:
                            # Read the resource
                            resource_data = handle_resource_read(resource_uri, interface)

                            response = {
                                'jsonrpc': '2.0',
                                'id': request_id,
                                'result': resource_data
                            }
                    else:
                        logger.error(f"Unknown JSON-RPC method: {method}")
                        response = {
                            'jsonrpc': '2.0',
                            'id': request_id,
                            'error': {
                                'code': -32601,
                                'message': f'Method not found: {method}'
                            }
                        }
                else:
                    # Handle legacy custom format
                    logger.info("Detected custom format message")
                    command = command_data.get("command")
                    params = command_data.get("params", {})

                    if not command:
                        logger.error("Missing command field")
                        response = {
                            "success": False,
                            "message": "Missing command",
                            "errorDetails": "The command field is required"
                        }
                    else:
                        # Handle command
                        response = interface.handle_command(command, params)

                # Send response
                logger.debug(f"Sending response: {response}")
                print(json.dumps(response))
                sys.stdout.flush()

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON input: {str(e)}")
                response = {
                    "success": False,
                    "message": "Invalid JSON input",
                    "errorDetails": str(e)
                }
                print(json.dumps(response))
                sys.stdout.flush()

    except KeyboardInterrupt:
        logger.info("KiCAD interface stopped")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
