from django.db import migrations

FORWARD_SQL = """
CREATE FUNCTION enforce_offer_identity() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.seller_id IS DISTINCT FROM OLD.seller_id
       OR NEW.product_id IS DISTINCT FROM OLD.product_id THEN
        RAISE EXCEPTION 'An offer seller and product cannot be reassigned.'
            USING ERRCODE = '23514', CONSTRAINT = 'offer_identity_immutable';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER offer_identity_immutable
BEFORE UPDATE ON catalog_offer
FOR EACH ROW EXECUTE FUNCTION enforce_offer_identity();
"""

REVERSE_SQL = """
DROP TRIGGER offer_identity_immutable ON catalog_offer;
DROP FUNCTION enforce_offer_identity();
"""


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]
    operations = [migrations.RunSQL(FORWARD_SQL, REVERSE_SQL)]
