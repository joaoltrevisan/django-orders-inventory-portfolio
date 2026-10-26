# Django Orders and Inventory Portfolio

A back-end portfolio project demonstrating relational modeling, PostgreSQL integrity constraints, transactional inventory, authorization, automated tests, SQL reports, and evidence-based index optimization.

Repository: [joaoltrevisan/django-orders-inventory-portfolio](https://github.com/joaoltrevisan/django-orders-inventory-portfolio).

## Current delivery

**Stage 1: requirements, business rules, order lifecycle, and data model. Technical review is pending.**

This new repository currently contains design documents only. The existing related project was inspected before creating these files and remains unchanged. No application, database, migrations, Docker services, SQL reports, or benchmark has been implemented or executed in this repository yet. Historical test counts and performance measurements from the related project are not results for this project.

| Document | Contents |
| --- | --- |
| [Initial assessment](docs/stage-01/assessment.md) | Inspected baseline, reuse candidates, gaps, selected stack, and version evidence |
| [Requirements and business rules](docs/stage-01/requirements.md) | Scope, permissions, validation, lifecycle, stock strategy, transactions, and acceptance criteria |
| [Relational data model](docs/stage-01/data-model.md) | Mermaid ER diagram, tables, keys, constraints, indexes, and integrity boundaries |
| [Verification record](docs/stage-01/verification.md) | Commands actually executed, results, limitations, and review checklist |

## Planned stack

Python 3.12, Django 5.2 LTS, Django REST Framework, PostgreSQL 17, JWT authentication, Docker, and Docker Compose. Exact versions observed in the reusable environment and the remaining compatibility checks are recorded in the assessment. Stage 2 will pin and verify the new environment rather than assume that the previous installation proves this one works.

## Core design

- Customers register, authenticate, maintain their own profile, and access only their own orders.
- Administrators manage products, inventory, customers, and order processing.
- Creating an order atomically deducts available stock and records reservation movements.
- Cancelling a pending order restores its stock exactly once. Later states cannot be cancelled.
- Order items preserve purchase-time product names, SKUs, and decimal unit prices.
- Product and stock locks are acquired in ascending product ID order to prevent overselling and reduce deadlock risks.
- Financial reports count simulated approved payments for `PAID`, `SHIPPED`, and `DELIVERED` orders; no real payment processing is included.

## Delivery sequence

| Stage | Deliverable | Status |
| --- | --- | --- |
| 1 | Requirements, business rules, lifecycle, data model | Ready for technical review |
| 2 | Project setup, PostgreSQL, models, constraints, migrations, schema export | Pending |
| 3 | Authentication, customer management, products, permissions | Pending |
| 4 | Orders, stock ledger, transactions, controlled concurrency tests | Pending |
| 5 | Separate fictional datasets, executed SQL portfolio, measured index experiment | Pending |
| 6 | Final English documentation, OpenAPI, Docker guide, curl examples, portfolio presentation | Pending |

Each stage ends with actual verification evidence and a technical review pause. English commits will be published incrementally. No later stage starts before the current stage is reviewed.

## Execution and evidence

There is no application startup command yet. Docker instructions, a safe `.env.example`, migrations, PostgreSQL tests, data-generation commands, and API examples will be added as their implementation stages are completed.

Only fictional people and `example.com` customer email addresses will be used. Passwords will use Django hashing. Secrets and private database copies must remain outside Git. Performance claims will require preserved execution plans, repeated measurements, and equivalent query results.
