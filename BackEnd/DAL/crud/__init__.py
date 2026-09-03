"""Persistence queries, grouped by endpoint division.

DAL/crud functions only take DB sessions, IDs, or model instances and perform
persistence -- they must never be handed a FastAPI object and must never call
up into BL or routers.
"""
