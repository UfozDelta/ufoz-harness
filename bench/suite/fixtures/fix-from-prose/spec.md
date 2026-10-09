# Spec (fix-from-prose): money amounts round the wrong way on exact halves

Our price display rounds money amounts the wrong way when the amount ends in exactly half of the last digit. A price of 0.125 shows as $0.12, but it should show as $0.13, and -0.125 should show as -$0.13. Amounts should be read from the decimal text they were written as (2.675 is 2.675, not the nearest binary float), and a half always rounds away from zero. `format_money` should show the rounded value in dollars with thousands separators, for example `$1,234.50` or `-$1,234.57`.
