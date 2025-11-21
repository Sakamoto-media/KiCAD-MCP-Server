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
}
