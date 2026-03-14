Make a plan to achieve the following. The output of this analysis will be generated in a separate bar.

Name that bar CNC

2. GEOMETRY ANALYSIS (which library or tool inside our program is best suited for this?)
   
   - Extract all edges from the shape
   - For each edge, determine if it is a concave internal edge (internal to a pocket or slot)
   - Measure the radius of curvature at concave edges
   - Classify each flagged edge into three tiers:
     * CRITICAL: radius = 0 (sharp corner, not machinable)
     * WARNING: radius > 0 and < 1.5mm (requires specialist small end mill)
     * OK: radius >= 3mm (standard tooling compatible)
     * CAUTION (between WARNING and OK): radius >= 1.5mm and < 3mm
   - Also compute: pocket depth for each flagged corner if determinable, 
     to flag depth-to-radius ratio as an aggravating factor

3. RENDER VIEWS for vision analysis
   - Use pythonOCC offscreen rendering (OCC.Core.Graphic3d / V3d or use 
     FreeCAD headless) to generate three orthographic views of the part: 
     front, top, side as PNG images
   - Pass these three images to an LLM vision model (OpenAI GPT-4o or 
     Anthropic Claude) with the following prompt injected programmatically:
     "You are a manufacturing engineer reviewing a CNC part. 
      Examine these three orthographic views and identify: 
      (1) any internal pocket or slot features with visually sharp or 
      very tight corners, (2) any features that appear difficult to 
      access with standard milling tools, (3) any annotations or notes 
      visible on the views relevant to corner radii or surface finish. 
      Return your findings as structured JSON with fields: 
      flagged_features (list), general_observations (string), 
      confidence (low/medium/high)."
   - Merge vision model JSON output with geometry analysis results

4. REPORT GENERATION — PDF output using reportlab or weasyprint
   The PDF should have exactly three sections:

   SECTION 1 — Summary Box (traffic light)
   - Part filename
   - Count of CRITICAL / WARNING / CAUTION / OK corners
   - Overall machinability score (0-100, computed from weighted flags)
   - One-line cost impact statement (HIGH / MODERATE / LOW)

   SECTION 2 — Corner Detail Table
   Columns: Corner ID | Location Description | Measured Radius | 
   Minimum Tool Required | Status | Recommendation
   - Populate from geometry analysis results
   - Color-code rows: red / yellow / green

   SECTION 3 — Designer Guidance (plain English)
   - Static template text explaining WHY internal corners matter in CNC
   - Dynamic insertion of: how many corners need fixing, what radius 
     to change them to, estimated impact statement
   - Rule of thumb box: "Internal corners ≥ R3mm for aluminum, 
     ≥ R4mm for steel"

5. PROJECT STRUCTURE
   Propose a project structure, that doesnt disturb our current dfm review bar structure.



