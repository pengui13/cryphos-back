import logging
from decimal import Decimal

from assets.models import Quote
from bots.models import BotBalance, BotSignal
from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def quote_update(self):
        updated_count = 0

        balances_with_pending = BotBalance.objects.filter(signals__status="Pending").distinct()

        for balance in balances_with_pending:
            try:
                positions = BotSignal.objects.filter(balance=balance, status="Pending")

                unrealised_pnl = Decimal("0")

                for pos in positions:
                    with transaction.atomic():
                        try:
                            position = BotSignal.objects.select_for_update(nowait=True).get(
                                pk=pos.pk
                            )

                            quote = (
                                Quote.objects.filter(symbol=position.asset, interval="1MIN")
                                .order_by("-time")
                                .first()
                            )

                            if not quote:
                                self.stdout.write(
                                    f"No quote found for position {position.id}, asset {position.asset}"
                                )
                                continue

                            current_price = Decimal(quote.lp)

                            if position.quantity is None or position.entry_price is None:
                                self.stdout.write(
                                    f"Position {position.id} missing quantity or entry price"
                                )
                                continue

                            leverage = 1
                            init_value = position.quantity * position.entry_price
                            amount = Decimal(position.quantity)

                            # Calculate PNL and ROI
                            current_value = Decimal(leverage) * current_price * amount
                            value_difference = current_value - init_value
                            pnl = (
                                Decimal(1) if position.is_long else Decimal(-1)
                            ) * value_difference

                            # Debug print before saving
                            old_pnl = position.pnl
                            old_roi = position.roi

                            # Update the position
                            position.pnl = pnl
                            if init_value != 0:
                                position.roi = (pnl / init_value) * Decimal(100)
                            else:
                                position.roi = Decimal("0")

                            # Check for take profit or stop loss
                            if (
                                position.roi >= balance.take_profit
                                or position.roi <= balance.stop_loss
                            ):
                                # Close the position
                                position.status = "Closed"
                                position.save()

                                # Update balance in the same transaction
                                balance.current_balance += position.pnl
                                balance.save(update_fields=["current_balance"])

                            else:
                                # Regular update for open position
                                position.save(update_fields=["pnl", "roi"])
                                # Add to unrealized PNL
                                unrealised_pnl += position.pnl

                            updated_count += 1

                            # Debug print after saving
                            self.stdout.write(
                                f"Updated position {position.id}: PNL changed from {old_pnl} to {position.pnl}, ROI from {old_roi} to {position.roi}"
                            )

                        except BotSignal.DoesNotExist:
                            self.stdout.write(f"Position {pos.pk} no longer exists")
                            continue
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f"Error updating position {pos.pk}: {str(e)}")
                            )
                            logger.exception(f"Error updating position {pos.pk}")
                            continue

                balance.unrealised_pnl = unrealised_pnl
                balance.save(update_fields=["unrealised_pnl"])

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing balance {balance.id}: {str(e)}")
                )
                logger.exception(f"Error processing balance {balance.id}")

        self.stdout.write(f"Updated {updated_count} positions")

    def handle(self, *args, **options):
        self.stdout.write("Starting position update loop")
        try:
            try:
                self.quote_update()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Major error in update loop: {str(e)}"))
                logger.exception("Major error in update loop")

        except KeyboardInterrupt:
            self.stdout.write("Update loop terminated by user")
