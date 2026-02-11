from django.db.models import Exists, OuterRef
from django.db import transaction
from assets.models import HistQuotes

mapping = {
    "1m": "1MIN",
    "5m": "5MIN",
    "15m": "15MIN",
    "30m": "30MIN",
    "1h": "1HRS",
    "1d": "1DAY",
}


def normalize_intervals():
    with transaction.atomic():
        total_updated = 0
        for old, new in mapping.items():
            safe_qs = HistQuotes.objects.filter(interval=old).exclude(
                Exists(
                    HistQuotes.objects.filter(
                        symbol_id=OuterRef("symbol_id"),
                        time=OuterRef("time"),
                        interval=new,
                    )
                )
            )
            u1 = safe_qs.update(interval=new)
            print(f"[{old}->{new}] safe update: {u1}")
            total_updated += u1

            # 2) Удаляем «старые» дубли (оставляем запись с new)
            dup_qs = HistQuotes.objects.filter(interval=old).filter(
                Exists(
                    HistQuotes.objects.filter(
                        symbol_id=OuterRef("symbol_id"),
                        time=OuterRef("time"),
                        interval=new,
                    )
                )
            )
            d = dup_qs.delete()[0]
            if d:
                print(f"[{old}->{new}] deleted duplicates: {d}")

            # 3) Догоняем остаток
            u2 = HistQuotes.objects.filter(interval=old).update(interval=new)
            print(f"[{old}->{new}] final update: {u2}")
            total_updated += u2

        print(f"✅ Done. Total rows updated: {total_updated}")


normalize_intervals()
