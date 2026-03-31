#!/bin/bash

# ArtMap 프로젝트 실행 스크립트

echo "🚀 Starting ArtMap..."

# 1. Docker 컨테이너 시작
echo "📦 Starting PostgreSQL database..."
make docker-up

# 2. 데이터 수집 (자동으로 테이블 생성됨)
echo ""
echo "🎨 Ingesting artworks from Met Museum..."
python3 scripts/ingest_met_artworks.py

echo ""
echo "✅ ArtMap is ready!"
