# Subscription Migration Plan: Old Model to Credit-Based Model

## Overview

This document outlines the plan for migrating existing subscribers from the old subscription model to the new credit-based subscription model. The migration will be performed in phases to ensure a smooth transition for users and minimize disruption to the service.

## Migration Mapping

| Old Subscription Type | New Subscription Type | Credits | Benefits                                |
| --------------------- | --------------------- | ------- | --------------------------------------- |
| Monthly Subscription  | Gold Monthly          | 800     | Monthly credit allocation               |
| Yearly Subscription   | Platinum Yearly       | 2500    | Monthly credit allocation (higher tier) |

## Migration Process

### Phase 1: Preparation (1-2 weeks)

1. **Create and test migration scripts**

   - Develop scripts to list all active subscriptions
   - Develop scripts to identify subscriptions that need migration
   - Test scripts in a staging environment

2. **Prepare communication materials**

   - Draft email templates for different user segments
   - Create in-app notifications
   - Update help documentation to explain the new credit system

3. **Set up monitoring**
   - Implement tracking for migration success/failure
   - Set up alerts for any issues during migration

### Phase 2: User Communication (1 week before migration)

1. **Send pre-migration notifications**

   - Email all affected users about the upcoming change
   - Explain benefits of the new credit-based system
   - Provide timeline for the migration

2. **Display in-app notifications**

   - Show banners or modals to affected users
   - Link to more detailed information about the change

3. **Train support team**
   - Brief customer support on the migration details
   - Prepare FAQs for common questions
   - Set up dedicated support channels for migration issues

### Phase 3: Migration Execution (During low-traffic period)

1. **Backup database**

   - Take a full backup of the production database
   - Verify backup integrity

2. **Run migration in dry-run mode**

   - Generate a detailed migration plan
   - Review the plan for any potential issues
   - Export the plan for reference

3. **Execute migration**

   - Run the migration script with the execute flag
   - Monitor progress in real-time
   - Address any issues immediately

4. **Verify migration success**
   - Check a sample of migrated subscriptions
   - Verify credit allocation is working correctly
   - Monitor for any unusual system behavior

### Phase 4: Post-Migration (1 week after)

1. **Send confirmation emails**

   - Notify users that their subscription has been migrated
   - Explain their new credit allocation
   - Provide resources for learning more about the credit system

2. **Monitor and address issues**

   - Closely track user feedback and support tickets
   - Fix any issues promptly
   - Make adjustments to credit allocations if necessary

3. **Collect feedback**
   - Survey users about their experience
   - Gather insights for future improvements

## Technical Implementation

### Migration Scripts

We have created two main scripts to facilitate the migration:

1. **list_stripe_subscriptions.py**

   - Lists all active subscriptions from Stripe
   - Shows customer details, subscription info, and end dates
   - Can filter by subscription period (monthly/yearly)
   - Can export results to CSV

   Usage:

   ```
   ./list_stripe_subscriptions.py [--period=monthly|yearly] [--export=filename.csv] [--all]
   ```

2. **migrate_to_credit_subscriptions.py**

   - Identifies subscriptions that need migration
   - Maps old subscriptions to new credit-based packages
   - Provides a preview of changes in dry-run mode
   - Can execute the actual migration

   Usage:

   ```
   ./migrate_to_credit_subscriptions.py [--dry-run] [--execute] [--export=filename.csv]
   ```

### Database Changes

The migration will update the following in the database:

1. **UserSubscription table**

   - Update `package_id` to the new credit package
   - Store the previous package ID in `previous_package_id`
   - Update `credits_per_period` based on the new package

2. **Stripe Subscription**
   - Update the price ID to the new credit-based package
   - Add metadata to track the migration

## Rollback Plan

In case of issues, we have a rollback strategy:

1. **Immediate issues during migration**

   - Stop the migration process
   - Revert any changed subscriptions using the stored previous_package_id
   - Notify affected users about the delay

2. **Post-migration issues**
   - If isolated issues: Fix on a case-by-case basis
   - If widespread issues: Consider full rollback to previous subscription model

## Timeline

| Task                      | Timeframe        | Owner                 |
| ------------------------- | ---------------- | --------------------- |
| Script development        | Week 1           | Engineering           |
| Testing in staging        | Week 1-2         | Engineering           |
| Communication prep        | Week 1-2         | Marketing             |
| Support team training     | Week 2           | Customer Support      |
| User notifications        | Week 2           | Marketing             |
| Database backup           | Day of migration | DevOps                |
| Migration execution       | Day of migration | Engineering           |
| Post-migration monitoring | Week 3-4         | Engineering & Support |
| Feedback collection       | Week 4           | Product               |

## Success Criteria

The migration will be considered successful when:

1. All eligible subscriptions are migrated to the new model
2. Users can access and use their credits as expected
3. Billing continues to work correctly
4. Support ticket volume returns to normal levels after the initial period

## Appendix

### FAQ for Users

**Q: Why are you changing to a credit-based system?**
A: The credit-based system gives you more flexibility in how you use our services. Instead of being limited to specific features, you can use your credits for any feature you prefer.

**Q: Will I lose any benefits with this change?**
A: No, we've designed the new packages to provide equivalent or better value than your current subscription.

**Q: Do I need to do anything for this migration?**
A: No, the migration will happen automatically. You'll receive an email once your subscription has been migrated.

**Q: What happens to my billing date and amount?**
A: Your billing date will remain the same, and there will be no change to your subscription price.

### FAQ for Support Team

**Q: How do I check a user's new credit allocation?**
A: You can check the user's credit balance in the admin dashboard under User > Credits.

**Q: What if a user wants to keep their old subscription?**
A: The old subscription model is being phased out. Explain the benefits of the new credit system and offer assistance in understanding how to use credits.

**Q: How do I handle billing disputes related to the migration?**
A: Escalate to the billing team with the subject "Migration Billing Issue" and include the user's subscription ID and details of the dispute.
