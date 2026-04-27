import json
import os
import re
import io
import tempfile
import requests
from datetime import datetime, timedelta
from django.conf import settings
import google.generativeai as genai
import PIL.Image

# Configure Gemini
GEMINI_API_KEY = getattr(settings, 'GEMINI_API_KEY', '')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def clean_subject_name(text):
    """
    Standardized subject name cleaning for matching Theory and Lab components.
    Preserves digits that are part of subject identity (e.g. AD2, MLW 2).
    """
    if not text: return ""
    t = str(text).lower()
    # Remove course codes like CSE 2697, MTH-3003, etc.
    # We use a slightly more conservative regex to avoid catching short subject names
    t = re.sub(r'\b[a-z]{2,4}\s*[-]?\s*\d{3,5}\b', '', t)
    # Remove parentheses content like (T), (P), (Theory), (Lab)
    t = re.sub(r'[\(\[].*?[\)\]]', '', t)
    # Remove common lab/practical/theory suffixes
    t = re.sub(r'\s+(?:lab|practical|practicals|lab-i|lab-ii|p|t|pract|theory)\b', '', t)
    # Clean up multiple spaces
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def _download_link_as_image(link):
    """
    Downloads a file from a public link (Box, Google Drive, OneDrive, etc.)
    and returns a PIL Image object. Gemini cannot browse URLs, so we must
    download the content ourselves first.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # --- Strategy 1: Box enterprise shared links ---
    if 'box.com/s/' in link:
        return _download_from_box(link, headers)
    
    # --- Strategy 2: Google Drive ---
    elif 'drive.google.com' in link:
        if '/file/d/' in link:
            file_id = link.split('/file/d/')[1].split('/')[0]
            download_url = f'https://drive.google.com/uc?export=download&id={file_id}'
        else:
            download_url = link
        return _download_direct(download_url, headers)
    
    # --- Strategy 3: OneDrive ---
    elif '1drv.ms' in link or 'onedrive.live.com' in link:
        download_url = link.replace('redir?', 'download?')
        return _download_direct(download_url, headers)
    
    # --- Fallback: try direct download ---
    else:
        return _download_direct(link, headers)


def _download_from_box(link, headers):
    """
    Box enterprise links serve an HTML preview page.
    We parse the embedded JSON metadata to find the thumbnail/representation URL.
    """
    shared_name = link.split('/s/')[-1].split('?')[0].split('#')[0]
    
    # Step 1: Try the thumbnail URL pattern that Box exposes in og:image meta tag
    try:
        response = requests.get(link, headers=headers, timeout=30)
        response.raise_for_status()
        html = response.text
        
        # Extract og:image thumbnail URL from the HTML
        # Pattern: <meta property="og:image" content="https://app.box.com/representation/...">
        import re as _re
        og_match = _re.search(r'property="og:image"\s+content="([^"]+)"', html)
        if og_match:
            thumb_url = og_match.group(1)
            print(f"[Box] Found thumbnail URL: {thumb_url}")
            thumb_response = requests.get(thumb_url, headers=headers, timeout=30, allow_redirects=True)
            if thumb_response.status_code == 200 and 'image' in thumb_response.headers.get('Content-Type', ''):
                img = PIL.Image.open(io.BytesIO(thumb_response.content))
                img.thumbnail((1024, 1024))
                return img
        
        # Extract the JPG representation URL from Box.prefetchedData
        rep_match = _re.search(r'"representation":"jpg".*?"url_template":"([^"]+)"', html)
        if rep_match:
            rep_url = rep_match.group(1).replace('\\/', '/').replace('{+asset_path}', '1.jpg')
            print(f"[Box] Found representation URL: {rep_url}")
            rep_response = requests.get(rep_url, headers=headers, timeout=30, allow_redirects=True)
            if rep_response.status_code == 200:
                img = PIL.Image.open(io.BytesIO(rep_response.content))
                img.thumbnail((1024, 1024))
                return img
        
        # Try the authenticated_download_url from metadata
        dl_match = _re.search(r'"authenticated_download_url":"([^"]+)"', html)
        if dl_match:
            dl_url = dl_match.group(1).replace('\\/', '/')
            print(f"[Box] Found download URL: {dl_url}")
            dl_response = requests.get(dl_url, headers=headers, timeout=30, allow_redirects=True)
            if dl_response.status_code == 200:
                content_type = dl_response.headers.get('Content-Type', '')
                if 'image' in content_type:
                    img = PIL.Image.open(io.BytesIO(dl_response.content))
                    img.thumbnail((1024, 1024))
                    return img
                # For PDFs, save and return path
                if 'pdf' in content_type or 'octet-stream' in content_type:
                    temp_path = os.path.join(tempfile.gettempdir(), 'timetable_box.pdf')
                    with open(temp_path, 'wb') as f:
                        f.write(dl_response.content)
                    return temp_path

    except Exception as e:
        print(f"[Box] Primary extraction failed: {e}")
    
    # Step 2: Fallback — try shared/static pattern
    try:
        static_url = link.replace(f'/s/{shared_name}', f'/shared/static/{shared_name}')
        return _download_direct(static_url, headers)
    except Exception:
        pass
    
    raise Exception(
        "Could not download the file from Box. The link may require login or "
        "the file may not be publicly accessible. Please try sharing with "
        "'People with the link' access enabled."
    )


def _download_direct(url, headers):
    """Download a file directly and return as PIL Image or temp file path."""
    response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
    response.raise_for_status()
    
    content_type = response.headers.get('Content-Type', '')
    
    # Image — open directly
    if 'image' in content_type:
        img = PIL.Image.open(io.BytesIO(response.content))
        img.thumbnail((1024, 1024))
        return img
    
    # PDF or binary — try as image first, then save as temp file
    if 'pdf' in content_type or 'octet-stream' in content_type:
        try:
            img = PIL.Image.open(io.BytesIO(response.content))
            img.thumbnail((1024, 1024))
            return img
        except Exception:
            temp_path = os.path.join(tempfile.gettempdir(), 'timetable_download.tmp')
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            return temp_path
    
    # HTML — this is a preview page, not a file
    if 'html' in content_type:
        raise Exception("The link returned an HTML preview page instead of a file.")
    
    # Try as image anyway
    img = PIL.Image.open(io.BytesIO(response.content))
    img.thumbnail((1024, 1024))
    return img


def analyze_timetable(image_path=None, link=None):
    """
    Extracts timetable data from image or link using Google Gemini API.
    Returns the exact JSON schema expected by the views.
    """
    try:
        if not GEMINI_API_KEY:
            raise Exception("Gemini API key is missing.")
        
        model = genai.GenerativeModel('gemini-flash-lite-latest')
        contents = []
        
        if image_path and os.path.exists(image_path):
            img = PIL.Image.open(image_path)
            img.thumbnail((1024, 1024))
            contents.append(img)
            
        if link:
            # Download the file from the link first — Gemini cannot browse URLs
            downloaded = _download_link_as_image(link)
            if isinstance(downloaded, PIL.Image.Image):
                contents.append(downloaded)
            elif isinstance(downloaded, str) and os.path.exists(downloaded):
                # It's a file path (e.g. PDF saved to temp)
                try:
                    img = PIL.Image.open(downloaded)
                    img.thumbnail((1024, 1024))
                    contents.append(img)
                except Exception:
                    # Read as raw bytes and let Gemini try
                    with open(downloaded, 'rb') as f:
                        contents.append(f"[Downloaded file content from: {link}]")
        
        if not contents:
            raise Exception("No image or link provided for analysis, or the link could not be downloaded.")
            
        prompt = """
        Task: Read the uploaded timetable image and extract subjects with correct weekly attendance counts.

        STRICT RULES

        CRITICAL: WIDE BLOCK DETECTION MANDATE
        You MUST identify all blocks that span multiple time slots.
        If a theory block (non-lab) covers more than one time header, it MUST have units > 1.
        If you are even 1% unsure about the width of a theory block, you are FORBIDDEN from guessing units: 1.
        You MUST add it to the "_analytics.needs_clarification" list to ask the user.
        Example: If AD2 on Saturday visually appears wider than other single-slot blocks, you MUST ask.

        ZERO-HALLUCINATION TRANSCRIPTION RULE (MANDATORY)

        Phase 1: Transcription only
        Before any counting or reasoning, first transcribe each timetable cell EXACTLY as written.
        Rules:
        - Copy subject text exactly from the cell.
        - Do not add words. Do not remove words. Do not infer missing words.
        - CRITICAL ANTI-HALLUCINATION: NEVER APPEND THE WORD "LAB" UNLESS IT IS PHYSICALLY TYPED IN THE BOX.
        - If the cell says "AD2", you MUST output "AD2", NOT "AD2 LAB".
        - If the cell says "CSW2", you MUST output "CSW2", NOT "CSW2 LAB".
        - THIS IS A FATAL ERROR IF YOU VIOLATE IT.
        - Preserve the exact raw text shown in the timetable box.
        - Any subject classification must be based only on this exact transcription.
        - TIME-HEADER SPAN RULE: Do NOT estimate width using visible internal divider lines.
          For each theory block, determine span by checking how many timetable time-slot headers the block extends under.
          Count classes = number of time headers covered. Use header overlap to determine span.
          Example: If AD2 extends under two consecutive time headers, count 2 theory classes (units: 2), even if there is no vertical line visible inside the merged cell.
        - WIDE CELL SANITY CHECK: If a subject cell visually appears longer than neighboring single-slot cells, re-evaluate whether it covers multiple time headers before assigning units=1. Do not default to units=1 for unusually long merged cells.

        Phase 2: Validation gate
        Before marking any occurrence as lab, verify:
        Does the raw transcribed cell explicitly contain the token "LAB"?
        If NO: this occurrence cannot be labeled lab.
        If YES: label as lab.
        No exceptions.

        Phase 3:
        Only after transcription is frozen, apply counting rules.
        Transcription cannot be altered to satisfy later rules.
        Reasoning must follow transcription, never modify transcription.
        SELF-CHECK: If a subject is labeled as lab but the transcribed cell text does not contain "LAB", that is an error — correct it before final output.

        STEP 1 — FIRST READ THE SUBJECT LIST AT THE BOTTOM
        Classify each subject into:
        1. Theory only
        2. Lab only
        3. Theory + Lab

        Use legend/credits (example 3L-2P) for classification.

        --------------------------------------------------
        UNIVERSAL COUNTING RULES
        --------------------------------------------------
        WIDTH RULE APPLIES ONLY TO THEORY BLOCKS.
        If block is lab (is_lab: true):
        - count = 1 regardless of width.
        - Set "units": 1.
        
        If block is theory (is_lab: false):
        - count = number of slots spanned.
        - Set "units" = slot width.
        - Wider theory block counts by number of slots covered. Do NOT collapse theory blocks.

        --------------------------------------------------
        A) THEORY-ONLY SUBJECTS
        - NEVER ask user anything for theory-only subjects.
        - They are already fully determined from timetable.
        - Every occupied slot = 1 class.
        - Wider block counts by number of slots covered.
        - Consecutive theory periods count separately.
        - "X" means no class.

        --------------------------------------------------
        B) LAB-ONLY SUBJECTS
        - One continuous lab block = 1 lab attendance.
        - Even if spanning multiple slots, count once.
        - Set "units": 1 and "is_lab": true.

        --------------------------------------------------
        C) SUBJECTS HAVING BOTH THEORY + LAB (OR PRACTICALS)

        For subjects classified as Theory + Lab:
        - You MUST ask the user to specify the number of slots (attendance units) for EVERY day that subject occurs.
        - ADD an item to the "_analytics.needs_clarification" list.
        - Set "is_per_day_slot_clarification": true.
        - Set "subject": "[SubjectName]".
        - Set "days_occurring": ["Monday", "Wednesday", ...] (List all days this subject appears in the grid).
        - Set "reason": "This subject contains both Theory and Practicals. Please specify how many attendance slots (units) it counts for on each day it occurs."

        AMBIGUOUS WIDE BLOCK CHECK (FORCED DOUBT RULE):
        If a theory-only cell visually appears wider or longer than a standard single-slot cell, you are FORBIDDEN from assuming it is 1 slot.
        - Even if you think it is 1 slot, if the aspect ratio is wide, you MUST flag it as ambiguous.
        - ADD an item to the "_analytics.needs_clarification" list to ask the user.
        - Set "is_width_clarification": true in that item.
        - Include "day": "[Day]" in that item.
        - Prompt user exactly with this reason:
          "[SubjectName] on [Day] may span more than one slot. Is this block 1 slot or 2 slots wide?"

        --------------------------------------------------

        IMPORTANT
        DO NOT ask the "per-day-slot" question for:
        - Theory-only subjects (use Width Rule instead)
        - Lab-only subjects

        Ask ONLY for subjects classified as Theory + Lab.

        --------------------------------------------------

        PRIORITY RULE
        If a subject is Theory + Lab, the "is_per_day_slot_clarification" takes priority over all other rules for that subject.

        --------------------------------------------------
        OUTPUT FORMAT (respond ONLY with raw JSON, no markdown):
        {
            "Monday": ["Subject1", "Subject2"],
            "Tuesday": ["Subject3"],
            "_analytics": {
                "day_entries": {
                    "Monday": [
                        {"subject": "Subject1", "units": 1, "is_lab": false},
                        {"subject": "Subject2", "units": 2, "is_lab": false}
                    ],
                    "Tuesday": [
                        {"subject": "Subject3", "units": 1, "is_lab": false}
                    ]
                },
                "needs_clarification": [
                    {
                        "subject": "SubjectName",
                        "is_per_day_slot_clarification": true,
                        "days_occurring": ["Monday", "Wednesday"],
                        "reason": "This subject contains both Theory and Practicals. Please specify how many attendance slots (units) it counts for on each day it occurs."
                    }
                ],
                "total_weekly_classes": 4
            }
        }
        
        IMPORTANT: Include an entry in day_entries for EVERY day that has classes. The "total_weekly_classes" must equal the sum of all units across all days.
        Respond ONLY with raw JSON. No explanation, no markdown.
        """
        
        contents.append(prompt)
        response = model.generate_content(contents)
        text = response.text.strip()
        
        try:
            with open("debug_ai.txt", "a", encoding="utf-8") as f:
                f.write("=== AI TIMETABLE DEBUG ===\n")
                f.write(text + "\n==========================\n")
        except Exception:
            pass
        
        if "Please upload a clearer" in text:
             return {"_analytics": {"error": text, "total_weekly_classes": 0}}

        if text.startswith('```json'):
            text = text[7:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
        
        parsed = json.loads(text)
        
        # --- Post-processing safety net ---
        # If Gemini returned day_entries but total_weekly_classes is 0 or missing,
        # recompute it from the actual entries.
        analytics = parsed.get('_analytics', {}) if isinstance(parsed, dict) else {}
        day_entries = analytics.get('day_entries', {}) if isinstance(analytics, dict) else {}
        
        if isinstance(day_entries, dict) and day_entries:
            computed_total = 0
            classes_per_day = {}
            summary_by_subject = {}
            summary_by_base = {}

            for day, entries in day_entries.items():
                day_total = 0
                if isinstance(entries, list):
                    for entry in entries:
                        sub_raw = entry.get('subject', 'Unknown')
                        sub_base = clean_subject_name(sub_raw)
                        is_lab = entry.get('is_lab', False)
                        
                        if sub_base not in summary_by_base:
                            summary_by_base[sub_base] = {"has_theory": False, "has_lab": False, "days": set(), "names": set()}
                        summary_by_base[sub_base]["days"].add(day)
                        summary_by_base[sub_base]["names"].add(sub_raw)
                        if is_lab: summary_by_base[sub_base]["has_lab"] = True
                        else: summary_by_base[sub_base]["has_theory"] = True

                        try:
                            units = max(1, int(entry.get('units', 1)))
                        except (TypeError, ValueError):
                            units = 1
                        
                        day_total += units
                        computed_total += units

                        # Update Subject Summary
                        if sub_raw not in summary_by_subject:
                            summary_by_subject[sub_raw] = {
                                "Theory classes/week": 0,
                                "Lab classes/week": 0,
                                "Total attendance": 0
                            }
                        
                        if is_lab:
                            summary_by_subject[sub_raw]["Lab classes/week"] += units
                        else:
                            summary_by_subject[sub_raw]["Theory classes/week"] += units
                        summary_by_subject[sub_raw]["Total attendance"] += units

                classes_per_day[day] = day_total
            
            if '_analytics' not in parsed:
                parsed['_analytics'] = {}
            
            # --- Automatic Mixed Subject Detection ---
            if 'needs_clarification' not in parsed['_analytics']:
                parsed['_analytics']['needs_clarification'] = []
            
            for base, info in summary_by_base.items():
                if info["has_theory"] and info["has_lab"]:
                    grid_names = sorted(list(info["names"]))
                    display_subject = grid_names[0] # Use the actual name from the grid
                    
                    # Find if already flagged and update/add
                    flagged_item = next((c for c in parsed['_analytics']['needs_clarification'] if clean_subject_name(c.get('subject')) == base), None)
                    if flagged_item:
                        flagged_item['subject'] = display_subject # Update to use grid name
                        flagged_item['is_per_day_slot_clarification'] = True
                        flagged_item['days_occurring'] = sorted(list(info["days"]))
                    else:
                        parsed['_analytics']['needs_clarification'].append({
                            "subject": display_subject,
                            "is_per_day_slot_clarification": True,
                            "days_occurring": sorted(list(info["days"])),
                            "reason": f"Subject '{display_subject}' has both Theory and Lab sessions. Please specify the slots for each day."
                        })

            parsed['_analytics']['total_weekly_classes'] = computed_total
            parsed['_analytics']['classes_per_day'] = classes_per_day
            parsed['_analytics']['summary_by_subject'] = summary_by_subject
            print(f"[AI Post-Process] Recalculated totals: {computed_total} classes/week across {len(summary_by_subject)} subjects.")
        
        print(f"[AI Timetable] Final parsed result keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'not a dict'}")
        print(f"[AI Timetable] total_weekly_classes: {parsed.get('_analytics', {}).get('total_weekly_classes', 'N/A')}")
        
        return parsed

    except Exception as e:
        print(f"Gemini Timetable Error: {str(e)}")
        return {
            "_analytics": {
                "total_weekly_classes": 0,
                "error": str(e)
            }
        }

def analyze_academic_calendar(calendar_path, holiday_path=None):
    """
    Extract dates and holidays using Google Gemini API.
    """
    try:
        if not GEMINI_API_KEY:
            raise Exception("Gemini API key is missing.")

        model = genai.GenerativeModel('gemini-flash-lite-latest')
        
        contents = []
        if calendar_path and os.path.exists(calendar_path):
            img_cal = PIL.Image.open(calendar_path)
            img_cal.thumbnail((1024, 1024))
            contents.append(img_cal)
        if holiday_path and os.path.exists(holiday_path):
            img_hol = PIL.Image.open(holiday_path)
            img_hol.thumbnail((1024, 1024))
            contents.append(img_hol)
            
        prompt = """
        You are an Academic Timetable and Attendance Assistant. Extract academic milestones and holidays.

        ACADEMIC CALENDAR RULES:
        - Exclude: semester breaks, mid sem exams, end sem exams, revision periods, non-teaching weeks.
        - TREAT THEM AS HOLIDAYS.
        
        HOLIDAY RULES:
        - Extract all global mandatory holidays.
        - IGNORE Optional/Restricted holidays unless explicitly requested.
        
        FAILSAFE RULE:
        - If the document is unreadable, respond exactly with: "Please upload a clearer PDF/scan or provide a public file link. I need readable timetable grids and subject details for accurate calculation."

        Return ONLY a JSON object exactly matching this schema:
        {
            "global_holidays": [
                {"name": "Republic Day", "date": "YYYY-MM-DD"}
            ],
            "sem1": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "holidays": ["YYYY-MM-DD", "YYYY-MM-DD"]},
            "sem2": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "holidays": ["YYYY-MM-DD", "YYYY-MM-DD"]},
            "sem3": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "holidays": ["YYYY-MM-DD", "YYYY-MM-DD"]},
            "sem4": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "holidays": ["YYYY-MM-DD", "YYYY-MM-DD"]},
            "sem5": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "holidays": ["YYYY-MM-DD", "YYYY-MM-DD"]},
            "sem6": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "holidays": ["YYYY-MM-DD", "YYYY-MM-DD"]},
            "sem7": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "holidays": ["YYYY-MM-DD", "YYYY-MM-DD"]},
            "sem8": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "holidays": ["YYYY-MM-DD", "YYYY-MM-DD"]}
        }
        
        Rules:
        - Dates MUST be in "YYYY-MM-DD" format.
        - Map "Odd Semester" dates to sem1, 3, 5, 7.
        - Map "Even Semester" dates to sem2, 4, 6, 8.
        - If not specified, map to all semesters sem1-8.
        """
        contents.append(prompt)
        
        response = model.generate_content(contents)
        text = response.text.strip()
        
        if "Please upload a clearer" in text:
            return {"error": text}

        if text.startswith('```json'):
            text = text[7:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
        
        return json.loads(text)

    except Exception as e:
        print(f"Gemini Calendar Error: {str(e)}")
        return {"error": str(e), "global_holidays": []}

def get_ai_chat_response(message):
    """
    Handle chat messages for the Academic Timetable and Attendance Assistant.
    """
    try:
        if not GEMINI_API_KEY:
            return "I'm sorry, my AI brain (Gemini API key) is not connected right now!"
            
        model = genai.GenerativeModel('gemini-flash-lite-latest')
        
        prompt = f"""
        You are an Academic Timetable and Attendance Assistant.
        
        Your purpose is to help users analyze:
        - Timetables
        - Academic calendars
        - Holiday lists
        - Public file links (Box, OneDrive, Google Drive)

        GENERAL BEHAVIOR RULES:
        - Always prioritize accuracy over guessing.
        - Never estimate unreadable data.
        - If any document or link is unclear, respond: "Please upload a clearer PDF/scan or provide a public file link. I need readable timetable grids and subject details for accurate calculation."

        COUNTING RULES (Enforce these if asked about schedules):
        1. THEORY RULE: Every theory time slot = 1 SEPARATE CLASS. No merging of consecutive theory periods. Repeated theory subjects must be counted separately. If a theory block spans 2 or 3 periods, count it as 2 or 3 classes.
        2. LAB RULE: A continuous lab block = ONLY 1 LAB CLASS. Do not double-count a single continuous lab session. Separate lab sessions = separate counts.
        3. MIXED SUBJECTS: If a subject contains both Theory and Practicals, ask for the number of attendance slots for each day it occurs. Do not guess.

        ACADEMIC CALENDAR RULES:
        - Exclude semester breaks, exams, and non-teaching weeks (treat as holidays).

        MISSING LAB EXCEPTION:
        - If a subject has practicals but they aren't marked clearly, ask: "Your [Subject] has both theory and practicals. Please specify how many attendance slots it counts for on each day (Mon, Wed, etc.) it appears in your timetable."

        Keep your answers concise, friendly, and helpful. Use markdown formatting.
        
        Student message: {message}
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"I'm experiencing some technical difficulties. (Error: {str(e)})"

def calculate_total_classes(start_date_str, end_date_str, subject_name, timetable_dict, holidays_list):
    """
    Automated logic to calculate EXACT number of classes that will happen over the semester.
    """
    if not start_date_str or not end_date_str:
        return 0
        
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    
    # Format holidays
    holiday_dates = []
    for h in holidays_list:
        try:
            if isinstance(h, dict) and 'date' in h:
                holiday_dates.append(datetime.strptime(h['date'], "%Y-%m-%d").date())
            elif isinstance(h, str):
                holiday_dates.append(datetime.strptime(h, "%Y-%m-%d").date())
        except ValueError:
            pass
            
    analytics = timetable_dict.get('_analytics', {}) if isinstance(timetable_dict, dict) else {}
    subject_day_units = analytics.get('subject_day_units', {}) if isinstance(analytics, dict) else {}
    day_entries = analytics.get('day_entries', {}) if isinstance(analytics, dict) else {}

    # Prefer explicit day entries parsed from summary lines.
    if isinstance(day_entries, dict) and day_entries:
        total_classes = 0
        current_date = start_date
        while current_date <= end_date:
            if current_date not in holiday_dates:
                day_name = current_date.strftime('%A')
                entries = day_entries.get(day_name, []) if isinstance(day_entries.get(day_name), list) else []
                for entry in entries:
                    if entry.get('subject') == subject_name:
                        try:
                            total_classes += max(1, int(entry.get('units', 1)))
                        except (TypeError, ValueError):
                            total_classes += 1
            current_date += timedelta(days=1)
        return total_classes

    # Fallback: infer from day-wise subject arrays.
    days_of_week_taught = []
    day_map = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
    
    occurrences_per_day = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    for day_str, subjects in timetable_dict.items():
        if day_str not in day_map or not isinstance(subjects, list):
            continue
        count = subjects.count(subject_name)
        if count > 0 and day_str in day_map:
            day_idx = day_map[day_str]
            days_of_week_taught.append(day_idx)
            per_day_units = subject_day_units.get(subject_name, {}) if isinstance(subject_day_units, dict) else {}
            unit_value = per_day_units.get(day_str, count) if isinstance(per_day_units, dict) else count
            try:
                occurrences_per_day[day_idx] = max(1, int(unit_value))
            except (TypeError, ValueError):
                occurrences_per_day[day_idx] = count
            
    total_classes = 0
    current_date = start_date
    
    while current_date <= end_date:
        weekday = current_date.weekday()
        if weekday in days_of_week_taught:
            if current_date not in holiday_dates:
                total_classes += occurrences_per_day[weekday]
        current_date += timedelta(days=1)
        
    return total_classes
