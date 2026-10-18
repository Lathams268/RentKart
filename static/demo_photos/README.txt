RentKart demo photos
====================

Put REAL photos for seeded demo items in this folder. The project never
downloads, scrapes or copies images from other sites - only files you place
here are used, plus the existing drawings in ../illustrations/.

Photo lookup order (see utils/illustrations.py :: item_picture)
--------------------------------------------------------------
1. The item's own uploaded photo (a name that is NOT a legacy seed_<n>.png).
2. demo_photos/<item-slug>.(jpg|jpeg|png|webp)   (a photo for one specific item)
3. demo_photos/stock/<category>/<subcategory-key>.(jpg|jpeg|png|webp)
4. demo_photos/stock/<category>/default.(jpg|jpeg|png|webp)
5. The existing drawing for the sub-category, then the category drawing.

Real photos are shown with object-fit: cover in a fixed 4/3 box with a soft
rounded corner. Drawings keep their current look. An empty box is never shown.

Folder layout
-------------
demo_photos/
    <item-slug>.jpg              one photo per item, named from its title
    stock/
        <category>/
            <subcategory-key>.jpg
            default.jpg
    _originals/                  auto-backup created by tools/photo_report.py --resize

Categories and sub-category keys
-------------------------------
clothes      : lehenga, saree, sherwani, kurta, kurta_set, kids_wear, western,
               gown, blazer, frock, anarkali
books        : comedy, spiritual, motivation, self_help, fiction, biography,
               mythology, children_books, education, business_books, health,
               poetry, other_books
farm_tools   : tractor, attachments, water_tank, sprayer, harvesting, hand_tools,
               power_tools, soil, transport
electronics  : camera, laptop, projector, speaker, microphone, drone, lights,
               generator, console, screen
event_items  : decoration, chairs, tent, stage_lighting, catering, stage,
               festival_items, photobooth

Photo guidelines
----------------
- Keep each file under 800 KB and no wider than 1600 px.
- Record the source of every photo in CREDITS.txt.
- Run:  python tools/photo_report.py            (see what exists / is missing)
- Run:  python tools/photo_report.py --resize   (shrink oversized photos)
