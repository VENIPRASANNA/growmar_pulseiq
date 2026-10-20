SELECT expense_id, amount_excl_gst, gst_amount, total_amount
FROM warehouse.fact_expense
WHERE ABS(total_amount - (amount_excl_gst + gst_amount)) > 0.01;
