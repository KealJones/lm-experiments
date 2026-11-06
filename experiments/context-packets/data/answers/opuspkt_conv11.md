Here's the math:

- Monthly revenue: $33,320.00
- Minus shipping total: $33,320.00 − $3,025.00 = $30,295.00
- Minus sales tax: $30,295.00 − $2,748.90 = **$27,546.10**

So what's left is **$27,546.10**.

In the sheet, it's just the revenue cell minus the other two. For example, if Monthly revenue is in B2, Shipping total in B3 and Sales tax amount in B4:

`=B2-B3-B4`

(Change the cell references to match your rows.)

One thing to watch: we calculated that $2,748.90 of tax *on top of* the $33,320, so it's money customers paid in addition to the mug price, and you pass it on to the tax authority. If your $33,320 doesn't include tax, subtracting the tax from it takes away money that was never in that number. In that case, what you actually keep after shipping is $30,295.00. The $27,546.10 figure is right only if the $33,320 is what customers paid *including* tax. Also, none of this takes out cost of goods or packaging yet, so it isn't profit.
