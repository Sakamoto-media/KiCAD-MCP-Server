/**
 * Schematic tools for KiCAD MCP server
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';

export function registerSchematicTools(server: McpServer, callKicadScript: Function) {
  // Create schematic tool
  server.tool(
    "create_schematic",
    "Create a new schematic",
    {
      name: z.string().describe("Schematic name"),
      path: z.string().optional().describe("Optional path"),
    },
    async (args: { name: string; path?: string }) => {
      const result = await callKicadScript("create_schematic", args);
      return {
        content: [{
          type: "text",
          text: JSON.stringify(result, null, 2)
        }]
      };
    }
  );

  // Add component to schematic
  server.tool(
    "add_schematic_component",
    "Add a component to the schematic",
    {
      symbol: z.string().describe("Symbol library reference"),
      reference: z.string().describe("Component reference (e.g., R1, U1)"),
      value: z.string().optional().describe("Component value"),
      position: z.object({
        x: z.number(),
        y: z.number()
      }).optional().describe("Position on schematic"),
    },
    async (args: any) => {
      const result = await callKicadScript("add_schematic_component", args);
      return {
        content: [{
          type: "text",
          text: JSON.stringify(result, null, 2)
        }]
      };
    }
  );

  // Connect components with wire
  server.tool(
    "add_wire",
    "Add a wire connection in the schematic",
    {
      start: z.object({
        x: z.number(),
        y: z.number()
      }).describe("Start position"),
      end: z.object({
        x: z.number(),
        y: z.number()
      }).describe("End position"),
    },
    async (args: any) => {
      const result = await callKicadScript("add_wire", args);
      return {
        content: [{
          type: "text",
          text: JSON.stringify(result, null, 2)
        }]
      };
    }
  );

  // Load schematic
  server.tool(
    "load_schematic",
    "Load an existing schematic file",
    {
      file_path: z.string().describe("Path to the .kicad_sch file"),
    },
    async (args: { file_path: string }) => {
      const result = await callKicadScript("load_schematic", args);
      return {
        content: [{
          type: "text",
          text: JSON.stringify(result, null, 2)
        }]
      };
    }
  );

  // Get all symbols
  server.tool(
    "get_all_symbols",
    "Get all symbols (components) from a schematic",
    {
      file_path: z.string().describe("Path to the .kicad_sch file"),
    },
    async (args: { file_path: string }) => {
      const result = await callKicadScript("get_all_symbols", args);
      return {
        content: [{
          type: "text",
          text: JSON.stringify(result, null, 2)
        }]
      };
    }
  );

  // Get symbol properties
  server.tool(
    "get_symbol_properties",
    "Get properties of a specific symbol by reference",
    {
      file_path: z.string().describe("Path to the .kicad_sch file"),
      reference: z.string().describe("Component reference (e.g., R1, U1)"),
    },
    async (args: { file_path: string; reference: string }) => {
      const result = await callKicadScript("get_symbol_properties", args);
      return {
        content: [{
          type: "text",
          text: JSON.stringify(result, null, 2)
        }]
      };
    }
  );

  // Update symbol property
  server.tool(
    "update_symbol_property",
    "Update a property of a specific symbol",
    {
      file_path: z.string().describe("Path to the .kicad_sch file"),
      reference: z.string().describe("Component reference (e.g., R1, U1)"),
      property: z.string().describe("Property name (e.g., Value, Footprint)"),
      value: z.string().describe("New property value"),
      output_path: z.string().optional().describe("Optional output path (defaults to overwriting input)"),
    },
    async (args: { file_path: string; reference: string; property: string; value: string; output_path?: string }) => {
      const result = await callKicadScript("update_symbol_property", args);
      return {
        content: [{
          type: "text",
          text: JSON.stringify(result, null, 2)
        }]
      };
    }
  );

  // Add symbol with exact coordinates (Method 1)
  server.tool(
    "add_symbol",
    "Add a symbol/component at exact coordinates using S-expression",
    {
      file_path: z.string().describe("Path to the .kicad_sch file"),
      lib_id: z.string().describe("Library ID in format Library:Component (e.g., Device:R, Device:C)"),
      reference: z.string().describe("Component reference (e.g., R1, C1, U1)"),
      value: z.string().describe("Component value (e.g., 10k, 100nF)"),
      x: z.number().describe("X coordinate in mm"),
      y: z.number().describe("Y coordinate in mm"),
      rotation: z.number().optional().describe("Rotation angle in degrees (default: 0)"),
      footprint: z.string().optional().describe("Footprint library ID (e.g., Resistor_SMD:R_0603_1608Metric)"),
      datasheet: z.string().optional().describe("Datasheet URL or path"),
      output_path: z.string().optional().describe("Optional output path (defaults to overwriting input)"),
    },
    async (args: { file_path: string; lib_id: string; reference: string; value: string; x: number; y: number; rotation?: number; footprint?: string; datasheet?: string; output_path?: string }) => {
      const result = await callKicadScript("add_symbol", args);
      return {
        content: [{
          type: "text",
          text: JSON.stringify(result, null, 2)
        }]
      };
    }
  );

  // Add symbol with automatic grid positioning (Method 2)
  server.tool(
    "add_symbol_auto",
    "Add a symbol/component with automatic grid-based positioning to avoid collisions",
    {
      file_path: z.string().describe("Path to the .kicad_sch file"),
      lib_id: z.string().describe("Library ID in format Library:Component (e.g., Device:R, Device:C)"),
      reference: z.string().describe("Component reference (e.g., R1, C1, U1)"),
      value: z.string().describe("Component value (e.g., 10k, 100nF)"),
      grid_x: z.number().optional().describe("Starting grid X position (default: 0)"),
      grid_y: z.number().optional().describe("Starting grid Y position (default: 0)"),
      grid_size: z.number().optional().describe("Grid size in mm (default: 50.8 = 2 inches)"),
      rotation: z.number().optional().describe("Rotation angle in degrees (default: 0)"),
      footprint: z.string().optional().describe("Footprint library ID"),
      datasheet: z.string().optional().describe("Datasheet URL or path"),
      output_path: z.string().optional().describe("Optional output path (defaults to overwriting input)"),
    },
    async (args: { file_path: string; lib_id: string; reference: string; value: string; grid_x?: number; grid_y?: number; grid_size?: number; rotation?: number; footprint?: string; datasheet?: string; output_path?: string }) => {
      const result = await callKicadScript("add_symbol_auto", args);
      return {
        content: [{
          type: "text",
          text: JSON.stringify(result, null, 2)
        }]
      };
    }
  );

  // Add symbol relative to another component (Method 3)
  server.tool(
    "add_symbol_relative",
    "Add a symbol/component positioned relative to an existing component",
    {
      file_path: z.string().describe("Path to the .kicad_sch file"),
      lib_id: z.string().describe("Library ID in format Library:Component (e.g., Device:R, Device:C)"),
      reference: z.string().describe("Component reference (e.g., R1, C1, U1)"),
      value: z.string().describe("Component value (e.g., 10k, 100nF)"),
      anchor_ref: z.string().describe("Reference of the anchor component to position relative to"),
      direction: z.string().optional().describe("Direction from anchor: right, left, below, above, below-right, below-left, above-right, above-left (default: right)"),
      distance: z.number().optional().describe("Distance from anchor in mm (default: 25.4 = 1 inch)"),
      rotation: z.number().optional().describe("Rotation angle in degrees (default: 0)"),
      footprint: z.string().optional().describe("Footprint library ID"),
      datasheet: z.string().optional().describe("Datasheet URL or path"),
      output_path: z.string().optional().describe("Optional output path (defaults to overwriting input)"),
    },
    async (args: { file_path: string; lib_id: string; reference: string; value: string; anchor_ref: string; direction?: string; distance?: number; rotation?: number; footprint?: string; datasheet?: string; output_path?: string }) => {
      const result = await callKicadScript("add_symbol_relative", args);
      return {
        content: [{
          type: "text",
          text: JSON.stringify(result, null, 2)
        }]
      };
    }
  );

  // Add multiple symbols in a group layout (Method 4)
  server.tool(
    "add_symbol_group",
    "Add multiple symbols/components in a grid layout at once",
    {
      file_path: z.string().describe("Path to the .kicad_sch file"),
      components: z.array(
        z.object({
          lib_id: z.string().describe("Library ID (e.g., Device:R)"),
          reference: z.string().describe("Component reference (e.g., R1)"),
          value: z.string().describe("Component value (e.g., 10k)"),
          footprint: z.string().optional().describe("Footprint library ID"),
          datasheet: z.string().optional().describe("Datasheet URL or path"),
        })
      ).describe("Array of components to add"),
      start_x: z.number().optional().describe("Starting X coordinate in mm (default: 100)"),
      start_y: z.number().optional().describe("Starting Y coordinate in mm (default: 100)"),
      spacing: z.number().optional().describe("Spacing between components in mm (default: 25.4 = 1 inch)"),
      columns: z.number().optional().describe("Number of columns before wrapping to next row (default: 5)"),
      output_path: z.string().optional().describe("Optional output path (defaults to overwriting input)"),
    },
    async (args: { file_path: string; components: Array<{lib_id: string; reference: string; value: string; footprint?: string; datasheet?: string}>; start_x?: number; start_y?: number; spacing?: number; columns?: number; output_path?: string }) => {
      const result = await callKicadScript("add_symbol_group", args);
      return {
        content: [{
          type: "text",
          text: JSON.stringify(result, null, 2)
        }]
      };
    }
  );
}
