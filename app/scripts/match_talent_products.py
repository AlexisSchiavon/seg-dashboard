"""One-time auto-match script: Talent <-> Pipedrive product (D-16/D-18/D-19).

Fuzzy-matches each Talent.name against the Pipedrive /products catalog using
rapidfuzz, and writes the matched product's id to
TalentProduct.pipedrive_product_id (D-15). Matches below THRESHOLD are
skipped and reported for manual review (D-18), along with any Pipedrive
products that remain unmapped after matching.

Run manually:
    uv run python -m app.scripts.match_talent_products
"""
from rapidfuzz import fuzz, process, utils

from app.database import SessionLocal
from app.integrations.pipedrive import _client, _paginate
from app.models import Talent, TalentProduct

THRESHOLD = 85

# Manual overrides for talents whose Pipedrive product name can't be resolved
# by the single-best-fuzzy-match loop below (D-19): two talents that perform
# together and share a single Pipedrive product.
MANUAL_PRODUCT_MATCHES = {
    "Don Silverio": "Don Silverio y Don Wicho",
    "Don Wicho": "Don Silverio y Don Wicho",
}

# Talents with no Pipedrive product yet (D-15) — always reported as unmatched,
# regardless of fuzzy score.
NO_PRODUCT_TALENTS = {"Dulce", "Tony Franco", "Casandra Salinas"}


def run(session_factory=SessionLocal):
    db = session_factory()
    client = _client()
    try:
        products = list(_paginate(client, "/products"))
        product_names = [p["name"] for p in products]
        products_by_name = {p["name"]: p for p in products}

        unmatched_talents = []
        for talent in db.query(Talent).all():
            if talent.name in NO_PRODUCT_TALENTS:
                unmatched_talents.append(talent.name)
                continue

            override_name = MANUAL_PRODUCT_MATCHES.get(talent.name)
            if override_name is not None:
                product = products_by_name.get(override_name)
                if product is None:
                    unmatched_talents.append(talent.name)
                    print(f"MISSING  {talent.name!r} -> {override_name!r} not found in Pipedrive products")
                    continue
                tp = db.query(TalentProduct).filter_by(talent_id=talent.id).first()
                if tp is None:
                    tp = TalentProduct(talent_id=talent.id)
                    db.add(tp)
                tp.pipedrive_product_id = product["id"]
                print(f"MATCHED  {talent.name!r} -> {product['name']!r} (manual override)")
                continue

            match = (
                process.extractOne(
                    talent.name, product_names, scorer=fuzz.WRatio, processor=utils.default_process
                )
                if product_names
                else None
            )
            if match and match[1] >= THRESHOLD:
                _name, score, idx = match
                product = products[idx]
                tp = db.query(TalentProduct).filter_by(talent_id=talent.id).first()
                if tp is None:
                    tp = TalentProduct(talent_id=talent.id)
                    db.add(tp)
                tp.pipedrive_product_id = product["id"]
                print(f"MATCHED  {talent.name!r} -> {product['name']!r} (score={score:.1f})")
            else:
                unmatched_talents.append(talent.name)
        db.commit()

        matched_product_ids = {
            tp.pipedrive_product_id
            for tp in db.query(TalentProduct).all()
            if tp.pipedrive_product_id is not None
        }
        unmapped_products = [p["name"] for p in products if p["id"] not in matched_product_ids]

        print("\n--- D-18: Unmapped Pipedrive products (manual review) ---")
        for name in unmapped_products:
            print(f"  - {name}")

        print("\n--- Talents with no match >= threshold (manual review) ---")
        for name in unmatched_talents:
            print(f"  - {name}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
