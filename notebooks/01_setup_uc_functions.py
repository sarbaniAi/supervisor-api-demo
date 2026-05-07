# Databricks notebook source
# MAGIC %md
# MAGIC # Step 1: Setup UC Functions for Supervisor API Demo
# MAGIC
# MAGIC This notebook creates Unity Catalog functions that will be used as tools by the Supervisor API.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create Schema (if not exists)

# COMMAND ----------

# MAGIC %sql
# MAGIC USE CATALOG `classic_stable_yh3b2z_catalog`;

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS `classic_stable_yh3b2z_catalog`.`supertvisor-api`;

# COMMAND ----------

# MAGIC %sql
# MAGIC USE SCHEMA `supertvisor-api`;

# COMMAND ----------

# MAGIC %md
# MAGIC ## UC Function 1: classify_priority
# MAGIC Classifies incident priority based on error rate, latency, and affected users.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE FUNCTION `classic_stable_yh3b2z_catalog`.`supertvisor-api`.classify_priority(
# MAGIC   error_rate DOUBLE COMMENT 'Current error rate percentage of the service',
# MAGIC   p99_latency_ms DOUBLE COMMENT 'P99 latency in milliseconds',
# MAGIC   affected_users INT COMMENT 'Estimated number of affected users'
# MAGIC )
# MAGIC RETURNS STRING
# MAGIC COMMENT 'Classifies incident priority (P1-P4) based on error rate, latency, and affected users. Use this to determine how urgently an issue needs to be addressed.'
# MAGIC RETURN
# MAGIC   CASE
# MAGIC     WHEN error_rate > 5.0 OR p99_latency_ms > 1000 OR affected_users > 10000 THEN 'P1 - Critical: Immediate response required (15 min SLA). Major customer impact detected.'
# MAGIC     WHEN error_rate > 2.0 OR p99_latency_ms > 500 OR affected_users > 1000 THEN 'P2 - High: Urgent response required (30 min SLA). Significant degradation detected.'
# MAGIC     WHEN error_rate > 0.5 OR p99_latency_ms > 300 OR affected_users > 100 THEN 'P3 - Medium: Standard response (4 hr SLA). Minor impact detected.'
# MAGIC     ELSE 'P4 - Low: Next business day. Minimal or no customer impact.'
# MAGIC   END;

# COMMAND ----------

# MAGIC %md
# MAGIC ## UC Function 2: calculate_sla_budget
# MAGIC Calculates remaining SLA error budget for a service.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE FUNCTION `classic_stable_yh3b2z_catalog`.`supertvisor-api`.calculate_sla_budget(
# MAGIC   uptime_percent DOUBLE COMMENT 'Current uptime percentage for the period (e.g., 99.85)',
# MAGIC   sla_target DOUBLE COMMENT 'SLA target percentage (e.g., 99.9)',
# MAGIC   days_in_period INT COMMENT 'Total days in the measurement period (e.g., 30)',
# MAGIC   days_elapsed INT COMMENT 'Days elapsed so far in the period'
# MAGIC )
# MAGIC RETURNS STRING
# MAGIC COMMENT 'Calculates the remaining SLA error budget for a service. Returns budget status, remaining downtime allowed, and risk assessment. Use this when evaluating whether a service can tolerate additional maintenance or incidents.'
# MAGIC RETURN
# MAGIC   CONCAT(
# MAGIC     'SLA Budget Report: ',
# MAGIC     'Target: ', CAST(sla_target AS STRING), '% | ',
# MAGIC     'Current: ', CAST(uptime_percent AS STRING), '% | ',
# MAGIC     'Allowed downtime (total period): ', CAST(ROUND((100 - sla_target) / 100 * days_in_period * 24 * 60, 1) AS STRING), ' minutes | ',
# MAGIC     'Downtime used: ', CAST(ROUND((100 - uptime_percent) / 100 * days_elapsed * 24 * 60, 1) AS STRING), ' minutes | ',
# MAGIC     'Budget remaining: ', CAST(ROUND(((100 - sla_target) / 100 * days_in_period * 24 * 60) - ((100 - uptime_percent) / 100 * days_elapsed * 24 * 60), 1) AS STRING), ' minutes | ',
# MAGIC     'Risk Level: ',
# MAGIC     CASE
# MAGIC       WHEN uptime_percent < sla_target THEN 'BREACHED - SLA violated!'
# MAGIC       WHEN (uptime_percent - sla_target) < 0.05 THEN 'CRITICAL - Less than 0.05% budget remaining'
# MAGIC       WHEN (uptime_percent - sla_target) < 0.1 THEN 'WARNING - Budget running low'
# MAGIC       ELSE 'HEALTHY - Sufficient budget remaining'
# MAGIC     END
# MAGIC   );

# COMMAND ----------

# MAGIC %md
# MAGIC ## UC Function 3: format_incident_summary
# MAGIC Formats an incident summary for communication to stakeholders.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE FUNCTION `classic_stable_yh3b2z_catalog`.`supertvisor-api`.format_incident_summary(
# MAGIC   service_name STRING COMMENT 'Name of the affected service',
# MAGIC   severity STRING COMMENT 'Incident severity (P1, P2, P3, P4)',
# MAGIC   error_rate DOUBLE COMMENT 'Current error rate percentage',
# MAGIC   latency_ms DOUBLE COMMENT 'Current P99 latency in milliseconds',
# MAGIC   description STRING COMMENT 'Brief description of the incident'
# MAGIC )
# MAGIC RETURNS STRING
# MAGIC COMMENT 'Formats a structured incident summary suitable for stakeholder communication. Use this to generate professional incident reports.'
# MAGIC RETURN
# MAGIC   CONCAT(
# MAGIC     '=== INCIDENT REPORT ===\n',
# MAGIC     'Service: ', service_name, '\n',
# MAGIC     'Severity: ', severity, '\n',
# MAGIC     'Status: ACTIVE\n',
# MAGIC     'Time: ', CAST(current_timestamp() AS STRING), '\n',
# MAGIC     '---\n',
# MAGIC     'Metrics:\n',
# MAGIC     '  Error Rate: ', CAST(error_rate AS STRING), '%\n',
# MAGIC     '  P99 Latency: ', CAST(latency_ms AS STRING), 'ms\n',
# MAGIC     '---\n',
# MAGIC     'Description: ', description, '\n',
# MAGIC     '---\n',
# MAGIC     'Impact: ',
# MAGIC     CASE
# MAGIC       WHEN severity = 'P1' THEN 'Customer-facing outage. All hands on deck.'
# MAGIC       WHEN severity = 'P2' THEN 'Service degradation. Active monitoring required.'
# MAGIC       WHEN severity = 'P3' THEN 'Minor issue. Standard remediation in progress.'
# MAGIC       ELSE 'Low priority. Scheduled for next maintenance window.'
# MAGIC     END,
# MAGIC     '\n=== END REPORT ==='
# MAGIC   );

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Functions

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Test classify_priority
# MAGIC SELECT `classic_stable_yh3b2z_catalog`.`supertvisor-api`.classify_priority(3.5, 600, 5000) AS priority;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Test calculate_sla_budget
# MAGIC SELECT `classic_stable_yh3b2z_catalog`.`supertvisor-api`.calculate_sla_budget(99.85, 99.9, 30, 15) AS sla_budget;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Test format_incident_summary
# MAGIC SELECT `classic_stable_yh3b2z_catalog`.`supertvisor-api`.format_incident_summary(
# MAGIC   'order-service', 'P2', 3.5, 600, 'Elevated error rates following deployment v2.4.1'
# MAGIC ) AS report;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Functions Created Successfully!
# MAGIC
# MAGIC The following UC functions are now available as Supervisor API tools:
# MAGIC - `classify_priority` - Classifies incident severity
# MAGIC - `calculate_sla_budget` - Calculates remaining SLA error budget
# MAGIC - `format_incident_summary` - Generates stakeholder incident reports
