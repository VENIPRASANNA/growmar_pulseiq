SELECT invoice_id, amount_paid, total_amount, balance_due
FROM warehouse.fact_invoice
WHERE amount_paid > total_amount + 0.01 OR balance_due < -0.01;
