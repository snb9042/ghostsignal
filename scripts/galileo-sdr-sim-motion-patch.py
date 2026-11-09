#!/usr/bin/env python3
"""Add -x user-motion-file support to galileo-sdr-sim (dynamic/continuous motion).
Reads the same 'time, lat_deg, lon_deg, height_m' 10Hz CSV that GhostSignal emits for GPS.
Assertion-guarded: each anchor must appear exactly once or the script aborts (no partial edits)."""
import sys

ROOT = "/root/galileo-sdr-sim"
edits = []  # (path, old, new, label)

# ---- main.cpp ----
MAIN = ROOT + "/src/main.cpp"

edits.append((MAIN,
    "    s.opt.navfile[0] = 0;\n    s.opt.tvfile[0] = 0;",
    "    s.opt.navfile[0] = 0;\n    s.opt.umfile[0] = 0;\n    s.opt.tvfile[0] = 0;",
    "main: init umfile"))

edits.append((MAIN,
    '"e:n:o:u:g:l:T:t:d:G:a:p:iI:U:b:vDr:"',
    '"e:n:o:u:g:l:x:T:t:d:G:a:p:iI:U:b:vDr:"',
    "main: add x: to optstring"))

edits.append((MAIN,
    "        case 'l':\n"
    "            sscanf(optarg, \"%lf,%lf,%lf\", &s.opt.llh[0], &s.opt.llh[1],\n"
    "                   &s.opt.llh[2]);\n"
    "            break;",
    "        case 'l':\n"
    "            sscanf(optarg, \"%lf,%lf,%lf\", &s.opt.llh[0], &s.opt.llh[1],\n"
    "                   &s.opt.llh[2]);\n"
    "            break;\n"
    "\n"
    "        case 'x':\n"
    "            strncpy(s.opt.umfile, optarg, MAX_CHAR - 1);\n"
    "            s.opt.umfile[MAX_CHAR - 1] = 0;\n"
    "            break;",
    "main: add case 'x'"))

# ---- galileo-sdr.cpp ----
GAL = ROOT + "/src/galileo-sdr.cpp"

edits.append((GAL,
    "    iduration = (int)(duration * 10.0 + 0.5);\n"
    "    numd = iduration;\n"
    "\n"
    "    for (int i = 0; i < numd; i++)\n"
    "        llh2xyz(llh, xyz[i].data());  // Convert llh to xyz for all steps",
    "    iduration = (int)(duration * 10.0 + 0.5);\n"
    "    numd = iduration;\n"
    "\n"
    "    if (s->opt.umfile[0] != 0)\n"
    "    {\n"
    "        // Dynamic mode: read user-motion file (time, lat_deg, lon_deg, height_m) @10Hz\n"
    "        FILE *umfp = fopen(s->opt.umfile, \"rt\");\n"
    "        if (umfp == NULL) { fprintf(stderr, \"ERROR: cannot open motion file %s\\n\", s->opt.umfile); exit(1); }\n"
    "        int umn = 0; char umln[256]; double umt, umlat, umlon, umh;\n"
    "        while (umn < USER_MOTION_SIZE && fgets(umln, sizeof(umln), umfp) != NULL)\n"
    "        {\n"
    "            if (sscanf(umln, \"%lf,%lf,%lf,%lf\", &umt, &umlat, &umlon, &umh) == 4 ||\n"
    "                sscanf(umln, \"%lf %lf %lf %lf\", &umt, &umlat, &umlon, &umh) == 4)\n"
    "            {\n"
    "                double umllh[3]; umllh[0] = umlat / R2D; umllh[1] = umlon / R2D; umllh[2] = umh;\n"
    "                llh2xyz(umllh, xyz[umn].data());\n"
    "                umn++;\n"
    "            }\n"
    "        }\n"
    "        fclose(umfp);\n"
    "        if (umn == 0) { fprintf(stderr, \"ERROR: no valid samples in motion file %s\\n\", s->opt.umfile); exit(1); }\n"
    "        numd = umn;\n"
    "        xyz2llh(xyz[0].data(), llh); // center satellite-visibility mask on first fix (RAD)\n"
    "        fprintf(stderr, \"\\nUsing dynamic motion mode: %d samples (%.1f s) from %s\\n\", numd, numd / 10.0, s->opt.umfile);\n"
    "    }\n"
    "    else\n"
    "    {\n"
    "        for (int i = 0; i < numd; i++)\n"
    "            llh2xyz(llh, xyz[i].data());  // Convert llh to xyz for all steps\n"
    "    }",
    "galileo-sdr: motion-file fill"))

edits.append((GAL,
    "    fprintf(stderr, \"\\nUsing static location mode.\\n\");\n"
    "    numd = iduration;",
    "    if (s->opt.umfile[0] == 0)\n"
    "    {\n"
    "        fprintf(stderr, \"\\nUsing static location mode.\\n\");\n"
    "        numd = iduration;\n"
    "    }",
    "galileo-sdr: guard static-mode print/numd"))

edits.append((GAL,
    "        // Copy contents of llh received over the locations thread\n"
    "        if (llhr != NULL)\n"
    "            memcpy(llh, llhr, 3 * sizeof(double));\n"
    "\n"
    "        llh[0] = llh[0] / R2D; // convert to RAD\n"
    "        llh[1] = llh[1] / R2D; // convert to RAD\n"
    "\n"
    "        if (iumd < (int)xyz.size())\n"
    "            llh2xyz(llh, xyz[iumd].data());",
    "        // In dynamic mode, xyz[iumd] is pre-filled from the motion file; don't overwrite it.\n"
    "        if (s->opt.umfile[0] == 0)\n"
    "        {\n"
    "            // Copy contents of llh received over the locations thread\n"
    "            if (llhr != NULL)\n"
    "                memcpy(llh, llhr, 3 * sizeof(double));\n"
    "\n"
    "            llh[0] = llh[0] / R2D; // convert to RAD\n"
    "            llh[1] = llh[1] / R2D; // convert to RAD\n"
    "\n"
    "            if (iumd < (int)xyz.size())\n"
    "                llh2xyz(llh, xyz[iumd].data());\n"
    "        }",
    "galileo-sdr: guard per-step static position update"))

# apply
cache = {}
for path, old, new, label in edits:
    if path not in cache:
        with open(path, "r", encoding="utf-8") as f:
            cache[path] = f.read()
    n = cache[path].count(old)
    if n != 1:
        sys.stderr.write(f"ABORT [{label}]: anchor found {n} times (expected 1) in {path}\n")
        sys.exit(2)
    cache[path] = cache[path].replace(old, new, 1)
    print(f"OK   [{label}]")

for path, text in cache.items():
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {path}")
print("PATCH COMPLETE")
