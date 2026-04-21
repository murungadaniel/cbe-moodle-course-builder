import html
import os
import re
import shutil
import xml.etree.ElementTree as ET
from xml.dom import minidom
from xml.sax.saxutils import escape as xml_escape

import pandas as pd

# Configuration
CSV_FILE = 'Automatic-Links.csv'
MASTER_TEMPLATE = 'template'  # Unpacked Moodle backup (same layout as .mbz contents)
BASE_GITHUB_URL = "https://innodems.github.io/CBC-Grade-10-Maths/external/lesson_plans/"
STUDENT_BASE_URL = "https://innodems.github.io/CBC-Grade-10-Maths/student/"
OUTPUT_DIR = "generated_backups"

SECTION_DIR_XML = os.path.join("sections", "section_2", "section.xml")
FORUM_XML = os.path.join("activities", "forum_2", "forum.xml")
COURSE_XML = os.path.join("course", "course.xml")


def slug_from_title(title_val):
    if title_val is None or (isinstance(title_val, float) and pd.isna(title_val)):
        return None
    s = str(title_val).strip().lower()
    if not s:
        return None
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or None


def folder_segment(row, filecase_col, title_col):
    """Prefer CSV filecase slug; otherwise derive from the human-readable title column."""
    if pd.notna(row.get(filecase_col)) and str(row[filecase_col]).strip():
        return str(row[filecase_col]).replace(" ", "_")
    return slug_from_title(row.get(title_col))


def lesson_title_from_row(row):
    """Deepest syllabus label present: subsubsection → subsection → section."""
    if pd.notna(row.get("Subsubsection")) and str(row["Subsubsection"]).strip():
        return str(row["Subsubsection"]).strip()
    if pd.notna(row.get("Subsection")) and str(row["Subsection"]).strip():
        return str(row["Subsection"]).strip()
    return str(row["Section"]).strip()


def course_topic_from_row(row):
    """Short topic string for the course summary placeholder."""
    return str(row["Section"]).strip()


def full_url(base, path_val):
    if path_val is None or (isinstance(path_val, float) and pd.isna(path_val)):
        return ""
    s = str(path_val).strip()
    if not s:
        return ""
    return base.rstrip("/") + "/" + s.lstrip("/")


def student_textbook_url(row):
    filecase = row.get("Section Filecase")
    if filecase is None or (isinstance(filecase, float) and pd.isna(filecase)):
        return ""
    section_slug = str(filecase).strip()
    if not section_slug:
        return ""
    section_slug = section_slug.replace(" ", "-")
    return STUDENT_BASE_URL.rstrip("/") + "/sec-" + section_slug.lstrip("-") + ".html"


def learning_objectives_entity_rows(row):
    """Build &lt;li&gt;...&lt;/li&gt; lines (HTML-entity encoded) for section summary."""
    lines = []
    for lo_col in ["LO 1", "LO 2", "LO 3", "LO 4"]:
        val = row.get(lo_col)
        if pd.notna(val) and str(val).strip():
            esc = html.escape(str(val).strip(), quote=True)
            lines.append(f"        &lt;li&gt;{esc}&lt;/li&gt;")
    if not lines:
        lines.append("        &lt;li&gt;&lt;/li&gt;")
    return "\n".join(lines)


def patch_section_summary_xml(text, row, lesson_title, forum_cm_id=2):
    lp_url = full_url(BASE_GITHUB_URL, row.get("Lesson Plan Path"))
    sbs_url = full_url(BASE_GITHUB_URL, row.get("Step By Step Guide Path"))
    safe_title = html.escape(lesson_title, quote=True)
    text = re.sub(
        r"<name> Lesson 1</name>",
        f"<name> {xml_escape(lesson_title)}</name>",
        text,
        count=1,
    )
    text = text.replace("[Lesson 1 title]", safe_title)
    text = text.replace("[inset url here]", lp_url or "#", 1)
    text = text.replace("[inset url here]", sbs_url or "#", 1)
    student_url = student_textbook_url(row)
    text = text.replace(
        "[Insert url for the student textbook on the relevant section or subsection]",
        student_url or "#",
        1,
    )
    ul_inner = learning_objectives_entity_rows(row)
    text = re.sub(
        r"&lt;ul&gt;\s*&lt;li&gt;\[Learning outcome 1\]&lt;/li&gt;\s*&lt;/ul&gt;",
        f"&lt;ul&gt;\n{ul_inner}\n      &lt;/ul&gt;",
        text,
        count=1,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"\$@FORUMVIEWBYID\*2@\$E",
        f"$@FORUMVIEWBYID*{forum_cm_id}@$E",
        text,
        count=1,
    )
    return text


def patch_forum_xml(text, lesson_title):
    t = xml_escape(lesson_title)
    text = re.sub(
        r"<name>Discussion: Lesson 1 title</name>",
        f"<name>Discussion: {t}</name>",
        text,
        count=1,
    )
    text = re.sub(
        r'<intro>Discuss your experience teaching the topic "\[Lesson 1 title\]" here</intro>',
        f'<intro>Discuss your experience teaching the topic "{t}" here</intro>',
        text,
        count=1,
    )
    return text


def patch_course_xml(text, row):
    topic = xml_escape(course_topic_from_row(row))
    return text.replace("[Insert topic name]", topic)


def patch_course_names(section_path, section_title, shortname_slug):
    """Set restored course fullname/shortname to the CSV Section title."""
    path = os.path.join(section_path, COURSE_XML)
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    text = re.sub(
        r"<shortname>[^<]*</shortname>",
        f"<shortname>{xml_escape(shortname_slug[:200])}</shortname>",
        text,
        count=1,
    )
    text = re.sub(
        r"<fullname>[^<]*</fullname>",
        f"<fullname>{xml_escape(section_title[:500])}</fullname>",
        text,
        count=1,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def patch_tail_section_numbers(section_path, n_lessons):
    """Renumber certificate and internal-files sections after inserting lessons."""
    mapping = [
        (os.path.join("sections", "section_10", "section.xml"), n_lessons + 1),
        (os.path.join("sections", "section_9", "section.xml"), n_lessons + 2),
    ]
    for rel, num in mapping:
        p = os.path.join(section_path, rel)
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()
        text = re.sub(r"<number>\d+</number>", f"<number>{num}</number>", text, count=1)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)


def patch_lesson_bundle_entry(section_path, row, sid, mid, section_number, forum_cm_id):
    """Fill one lesson (section + forum) from CSV row; ids match moodle_backup layout."""
    lesson_title = lesson_title_from_row(row)
    sec_rel = os.path.join("sections", f"section_{sid}", "section.xml")
    sp = os.path.join(section_path, sec_rel)
    with open(sp, "r", encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r'<section id="\d+"', f'<section id="{sid}"', text, count=1)
    text = re.sub(r"<number>\d+</number>", f"<number>{section_number}</number>", text, count=1)
    text = re.sub(r"<sequence>\d+</sequence>", f"<sequence>{mid}</sequence>", text, count=1)
    text = patch_section_summary_xml(
        text, row, lesson_title, forum_cm_id=forum_cm_id
    )
    with open(sp, "w", encoding="utf-8") as f:
        f.write(text)

    forum_rel = os.path.join("activities", f"forum_{mid}", "forum.xml")
    fp = os.path.join(section_path, forum_rel)
    with open(fp, "r", encoding="utf-8") as f:
        ftext = f.read()
    ftext = re.sub(
        r'<activity id="\d+" moduleid="\d+" modulename="forum" contextid="\d+">',
        f'<activity id="{mid}" moduleid="{mid}" modulename="forum" contextid="{500 + mid}">',
        ftext,
        count=1,
    )
    ftext = re.sub(r"<forum id=\"\d+\">", f'<forum id="{mid}">', ftext, count=1)
    ftext = patch_forum_xml(ftext, lesson_title)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(ftext)

    mod_rel = os.path.join("activities", f"forum_{mid}", "module.xml")
    mp = os.path.join(section_path, mod_rel)
    with open(mp, "r", encoding="utf-8") as f:
        mtext = f.read()
    mtext = re.sub(r'<module id="\d+"', f'<module id="{mid}"', mtext, count=1)
    mtext = re.sub(r"<sectionid>\d+</sectionid>", f"<sectionid>{sid}</sectionid>", mtext, count=1)
    mtext = re.sub(
        r"<sectionnumber>\d+</sectionnumber>",
        f"<sectionnumber>{section_number}</sectionnumber>",
        mtext,
        count=1,
    )
    with open(mp, "w", encoding="utf-8") as f:
        f.write(mtext)


def duplicate_lesson_from_master(section_path, master_template, sid, mid):
    """Copy pristine lesson section + forum from master template."""
    src_sec = os.path.join(master_template, "sections", "section_2")
    dst_sec = os.path.join(section_path, "sections", f"section_{sid}")
    src_forum = os.path.join(master_template, "activities", "forum_2")
    dst_forum = os.path.join(section_path, "activities", f"forum_{mid}")
    if os.path.exists(dst_sec):
        shutil.rmtree(dst_sec)
    if os.path.exists(dst_forum):
        shutil.rmtree(dst_forum)
    shutil.copytree(src_sec, dst_sec)
    shutil.copytree(src_forum, dst_forum)


def _backup_setting(level, name, value, section=None, activity=None):
    s = ET.Element("setting")
    ET.SubElement(s, "level").text = level
    if section is not None:
        ET.SubElement(s, "section").text = section
    if activity is not None:
        ET.SubElement(s, "activity").text = activity
    ET.SubElement(s, "name").text = name
    ET.SubElement(s, "value").text = value
    return s


def insert_extra_lessons_into_moodle_backup(moodle_backup_path, extra_specs):
    """
    extra_specs: list of dicts with keys sid, mid, title (lesson_title string).
    Inserts activity/section entries and matching settings after the first lesson.
    """
    if not extra_specs:
        return
    tree = ET.parse(moodle_backup_path)
    root = tree.getroot()
    info = root.find("information")
    contents = info.find("contents")
    acts = contents.find("activities")
    secs = contents.find("sections")
    settings_el = info.find("settings")

    act_children = list(acts)
    insert_act = next(
        i + 1
        for i, a in enumerate(act_children)
        if (a.find("directory") is not None and a.find("directory").text == "activities/forum_2")
    )
    pos = insert_act
    for spec in extra_specs:
        sid, mid, title = spec["sid"], spec["mid"], spec["title"]
        a = ET.Element("activity")
        ET.SubElement(a, "moduleid").text = str(mid)
        ET.SubElement(a, "sectionid").text = str(sid)
        ET.SubElement(a, "modulename").text = "forum"
        ET.SubElement(a, "title").text = f"Discussion: {title}"
        ET.SubElement(a, "directory").text = f"activities/forum_{mid}"
        ins = ET.SubElement(a, "insubsection")
        ins.text = ""
        acts.insert(pos, a)
        pos += 1

    sec_children = list(secs)
    insert_sec = next(
        i + 1
        for i, s in enumerate(sec_children)
        if (s.find("directory") is not None and s.find("directory").text == "sections/section_2")
    )
    pos = insert_sec
    for spec in extra_specs:
        sid, mid, title = spec["sid"], spec["mid"], spec["title"]
        s = ET.Element("section")
        ET.SubElement(s, "sectionid").text = str(sid)
        ET.SubElement(s, "title").text = f" {title}"
        ET.SubElement(s, "directory").text = f"sections/section_{sid}"
        ET.SubElement(s, "parentcmid").text = ""
        ET.SubElement(s, "modname").text = ""
        secs.insert(pos, s)
        pos += 1

    set_children = list(settings_el)
    insert_set = next(
        i
        for i, st in enumerate(set_children)
        if st.find("section") is not None and st.find("section").text == "section_10"
    )
    pos = insert_set
    for spec in extra_specs:
        sid, mid = spec["sid"], spec["mid"]
        sec_dir = f"section_{sid}"
        act_dir = f"forum_{mid}"
        settings_el.insert(
            pos,
            _backup_setting(
                "section", f"{sec_dir}_included", "1", section=sec_dir, activity=None
            ),
        )
        pos += 1
        settings_el.insert(
            pos,
            _backup_setting(
                "section", f"{sec_dir}_userinfo", "0", section=sec_dir, activity=None
            ),
        )
        pos += 1
        settings_el.insert(
            pos,
            _backup_setting(
                "activity",
                f"{act_dir}_included",
                "1",
                section=None,
                activity=act_dir,
            ),
        )
        pos += 1
        settings_el.insert(
            pos,
            _backup_setting(
                "activity",
                f"{act_dir}_userinfo",
                "0",
                section=None,
                activity=act_dir,
            ),
        )
        pos += 1

    write_xml_pretty(root, moodle_backup_path)


def section_bundle_folder_name(first_row):
    """One output folder per CSV Section (chapter + section filecase only)."""
    parts = []
    for fc_col, title_col in (
        ("Chapter Filecase", "Chapter"),
        ("Section Filecase", "Section"),
    ):
        seg = folder_segment(first_row, fc_col, title_col)
        if seg:
            parts.append(seg)
    return "_".join(parts) if parts else "bundle"


def apply_moodle_backup_bundle_metadata(
    moodle_backup_path, first_row, lesson_specs, course_fullname, course_shortname
):
    """Sync manifest titles for every lesson; CSV metadata from the first row of the bundle."""
    tree = ET.parse(moodle_backup_path)
    root = tree.getroot()
    info = root.find("information")
    if info is None:
        info = ET.SubElement(root, "information")

    for tag, val in (
        ("original_course_fullname", course_fullname),
        ("original_course_shortname", course_shortname),
    ):
        el = info.find(tag)
        if el is not None:
            el.text = val

    contents = info.find("contents")
    if contents is not None:
        acts = contents.find("activities")
        if acts is not None:
            for spec in lesson_specs:
                mid = spec["mid"]
                title = spec["title"]
                want = f"activities/forum_{mid}"
                for activity in acts.findall("activity"):
                    directory = activity.find("directory")
                    title_el = activity.find("title")
                    if (
                        directory is not None
                        and directory.text == want
                        and title_el is not None
                    ):
                        title_el.text = f"Discussion: {title}"
                        break
        secs = contents.find("sections")
        if secs is not None:
            for spec in lesson_specs:
                sid = spec["sid"]
                title = spec["title"]
                want = f"sections/section_{sid}"
                for section in secs.findall("section"):
                    directory = section.find("directory")
                    title_el = section.find("title")
                    if (
                        directory is not None
                        and directory.text == want
                        and title_el is not None
                    ):
                        title_el.text = f"{title}"
                        break

    hierarchy = info.find("hierarchy")
    if hierarchy is None:
        hierarchy = ET.SubElement(info, "hierarchy")
    else:
        for child in list(hierarchy):
            hierarchy.remove(child)

    row = first_row
    ET.SubElement(hierarchy, "chapter").text = str(row.get("Chapter", ""))
    ET.SubElement(hierarchy, "section").text = str(row.get("Section", ""))
    if pd.notna(row.get("Subsection")):
        ET.SubElement(hierarchy, "subsection").text = str(row["Subsection"])
    if pd.notna(row.get("Subsubsection")):
        ET.SubElement(hierarchy, "subsubsection").text = str(row["Subsubsection"])

    objectives = info.find("learning_objectives")
    if objectives is None:
        objectives = ET.SubElement(info, "learning_objectives")
    else:
        for child in list(objectives):
            objectives.remove(child)

    for lo_col in ["LO 1", "LO 2", "LO 3", "LO 4"]:
        lo_val = row.get(lo_col)
        if pd.notna(lo_val) and str(lo_val).strip() != "":
            lo_elem = ET.SubElement(objectives, "objective")
            lo_elem.text = str(lo_val).strip()
            lo_elem.set("level", lo_col)

    resources = info.find("resources")
    if resources is None:
        resources = ET.SubElement(info, "resources")
    else:
        for child in list(resources):
            resources.remove(child)

    lesson_plan_path = row.get("Lesson Plan Path")
    if pd.notna(lesson_plan_path) and str(lesson_plan_path).strip() != "":
        full_lp_url = (
            BASE_GITHUB_URL.rstrip("/") + "/" + str(lesson_plan_path).lstrip("/")
        )
        ET.SubElement(resources, "lesson_plan").text = full_lp_url

    step_by_step_path = row.get("Step By Step Guide Path")
    if pd.notna(step_by_step_path) and str(step_by_step_path).strip() != "":
        full_sbs_url = (
            BASE_GITHUB_URL.rstrip("/") + "/" + str(step_by_step_path).lstrip("/")
        )
        ET.SubElement(resources, "step_by_step_guide").text = full_sbs_url

    write_xml_pretty(root, moodle_backup_path)

def write_xml_pretty(root, filepath):
    """Write XML to file with proper formatting and declaration.

    Moodle's restore step calls convert_helper::detect_moodle2_format(), which
    only inspects the first ~200 bytes and requires the exact prologue:
    <?xml version="1.0" encoding="UTF-8"?>
    (see backup/util/helper/convert_helper.class.php in Moodle core).
    xml.dom.minidom emits <?xml version="1.0" ?> without encoding, which fails
    that check and yields 'Unknown backup format' on restore.
    """
    rough_string = ET.tostring(root, "utf-8")
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")
    lines = [line for line in pretty_xml.split("\n") if line.strip()]
    if lines and lines[0].startswith("<?xml"):
        lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    else:
        lines.insert(0, '<?xml version="1.0" encoding="UTF-8"?>')
    final_xml = "\n".join(lines)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(final_xml)


def patch_frontpage_student_link(section_path, row):
    path = os.path.join(section_path, "sections", "section_1", "section.xml")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    student_url = student_textbook_url(row) or "#"
    text = text.replace(
        "[Insert url for the student textbook on the relevant section or subsection]",
        student_url,
        1,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def process_data():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")

    df = pd.read_csv(CSV_FILE)
    df = df.dropna(subset=["Chapter", "Section"])
    print(f"Loaded CSV with {len(df)} valid rows after cleaning.")

    bundle_index = 0
    for (_chapter, _section), gdf in df.groupby(["Chapter", "Section"], sort=False):
        bundle_index += 1
        first = gdf.iloc[0]
        section_folder_name = section_bundle_folder_name(first)
        section_path = os.path.join(OUTPUT_DIR, section_folder_name)
        n_lessons = len(gdf)

        print(
            f"Processing bundle {bundle_index}: {first['Chapter']} — "
            f"{first['Section']} ({n_lessons} lesson(s))"
        )

        if os.path.exists(section_path):
            shutil.rmtree(section_path)
        shutil.copytree(MASTER_TEMPLATE, section_path)
        patch_frontpage_student_link(section_path, first)

        lesson_specs = []
        for j, (_, row) in enumerate(gdf.iterrows()):
            if j == 0:
                sid, mid = 2, 2
                patch_lesson_bundle_entry(
                    section_path, row, sid, mid, j + 1, forum_cm_id=2
                )
            else:
                sid = 10 + j
                mid = 17 + j
                duplicate_lesson_from_master(
                    section_path, MASTER_TEMPLATE, sid, mid
                )
                patch_lesson_bundle_entry(
                    section_path, row, sid, mid, j + 1, forum_cm_id=mid
                )
            lesson_specs.append(
                {
                    "sid": sid,
                    "mid": mid,
                    "title": lesson_title_from_row(row),
                }
            )

        patch_tail_section_numbers(section_path, n_lessons)

        moodle_backup_path = os.path.join(section_path, "moodle_backup.xml")
        if not os.path.exists(moodle_backup_path):
            print(f"Warning: moodle_backup.xml not found in {section_path}")
            continue

        extras = lesson_specs[1:]
        if extras:
            insert_extra_lessons_into_moodle_backup(moodle_backup_path, extras)

        course_path = os.path.join(section_path, COURSE_XML)
        if os.path.exists(course_path):
            with open(course_path, "r", encoding="utf-8") as f:
                course_text = f.read()
            course_text = patch_course_xml(course_text, first)
            with open(course_path, "w", encoding="utf-8") as f:
                f.write(course_text)

        sec_title = str(first["Section"]).strip()
        slug = section_folder_name or "course"
        patch_course_names(section_path, sec_title, slug)

        apply_moodle_backup_bundle_metadata(
            moodle_backup_path,
            first,
            lesson_specs,
            sec_title,
            slug,
        )

        arc = os.path.join(section_path, ".ARCHIVE_INDEX")
        if os.path.isfile(arc):
            os.remove(arc)

        print(f"Wrote bundle to {section_path}")

    print(
        f"Successfully generated {bundle_index} Moodle backup folder(s) in '{OUTPUT_DIR}' "
        f"(one per CSV Section)."
    )

if __name__ == "__main__":
    process_data()