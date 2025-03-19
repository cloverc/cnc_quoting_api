import ezdxf
from fastapi import FastAPI, File, UploadFile
from shapely.geometry import Polygon, LineString
import tempfile

app = FastAPI()

def extract_entities_from_block(doc, block_name, totals, part_areas, depth=0):
    """ Recursively extract geometry from nested blocks """
    if block_name not in doc.blocks:
        print(f"❌ Block '{block_name}' not found in document")
        return

    block = doc.blocks[block_name]
    indent = "   " * depth
    print(f"{indent}📦 Extracting from block '{block_name}':")

    for entity in block:
        print(f"{indent}   - {entity.dxftype()}")  # Print entity type

        if entity.dxftype() == "INSERT":
            sub_block_name = entity.dxf.name
            print(f"{indent}🔍 Found nested block: {sub_block_name}")
            extract_entities_from_block(doc, sub_block_name, totals, part_areas, depth + 1)

        elif entity.dxftype() == "LWPOLYLINE":
            points = [(p[0], p[1]) for p in entity.get_points()]
            poly = Polygon(points)

            if entity.is_closed and poly.is_valid:
                area = poly.area
                totals["total_part_area"] += area
                part_areas.append(area)
                totals["cut_length"] += poly.length
                print(f"{indent} LWPOLYLINE Area: {area}, Cut Length: {poly.length}")
            else:
                print(f"{indent} Skipping LWPOLYLINE (Not Closed or Invalid)")


        elif entity.dxftype() == "POLYLINE":
            points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]

            if len(points) > 2:
                poly = Polygon(points)
                if poly.is_valid and entity.is_closed:
                    area = poly.area
                    totals["total_part_area"] += area
                    part_areas.append(area)
                    totals["cut_length"] += poly.length
                    print(f"{indent}✅ POLYLINE Area: {area}, Cut Length: {poly.length}")
                else:
                    print(f"{indent}⚠️ Skipping POLYLINE (Not Closed or Invalid)")
        
        elif entity.dxftype() == "LINE":
            start = (entity.dxf.start.x, entity.dxf.start.y)
            end = (entity.dxf.end.x, entity.dxf.end.y)
            line = LineString([start, end])
            totals["cut_length"] += line.length
            print(f"{indent}✅ Added LINE cut length: {line.length}")

def extract_dxf_part_areas(file_path: str):
    """ Extract total part area and cut length from DXF file, including nested block geometry """
    try:
        print(f"DEBUG: Processing DXF file at path: {file_path}")

        try:
            doc = ezdxf.readfile(file_path)
        except Exception as e:
            print(f"ERROR: Failed to read DXF file - {e}")
            return {"error": f"DXF Processing Error: {str(e)}"}

        print("✅ DXF file loaded successfully")
        msp = doc.modelspace()

        totals = {"total_part_area": 0, "cut_length": 0}
        part_areas = []

        print("Entities in DXF file:")
        for entity in msp:
            print(f" - {entity.dxftype()}")

            if entity.dxftype() == "INSERT":
                block_name = entity.dxf.name
                print(f"🔍 Found a block reference: {block_name}")
                extract_entities_from_block(doc, block_name, totals, part_areas)

        print(f"📊 FINAL RESULTS: Total Area: {totals['total_part_area']}, Cut Length: {totals['cut_length']}")

        return {
            "total_part_area": totals["total_part_area"],
            "cut_length": totals["cut_length"],
            "part_areas": part_areas
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return {"error": f"DXF Processing Error: {str(e)}"}

@app.post("/process-dxf/")
async def process_dxf(file: UploadFile = File(...)):
    """ API endpoint to process DXF files and calculate sheets needed """
    try:
        if not file.filename.endswith(".dxf"):
            return {"error": "Only DXF files are allowed"}


        print(f"DEBUG: Uploading DXF File: {file.filename}")

        # Save the uploaded file as a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as temp_file:
            file_path = temp_file.name
            temp_file.write(await file.read())

        print(f"DEBUG: Saved DXF File at {file_path}")
        
        dxf_data = extract_dxf_part_areas(file_path)

        if "error" in dxf_data:
            return dxf_data

        return {
            "filename": file.filename,
            "total_part_area": dxf_data["total_part_area"],
            "cut_length": dxf_data["cut_length"],
            "part_areas": dxf_data["part_areas"]
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return {"error": f"File Processing Error: {str(e)}"}
