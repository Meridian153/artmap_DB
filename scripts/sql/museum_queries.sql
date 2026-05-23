-- ============================================================
-- 1. Artwork count per museum / 각 미술관별 작품 갯수
-- ============================================================
SELECT
    i.name_en   AS museum,
    i.name_ko   AS museum_ko,
    i.country_code,
    COUNT(ao.artwork_id) AS artwork_count
FROM institutions i
LEFT JOIN artwork_ownerships ao ON ao.institution_id = i.id
GROUP BY i.id, i.name_en, i.name_ko, i.country_code
ORDER BY artwork_count DESC;


-- ============================================================
-- 2. List of artworks per museum / 각 미술관에 속한 작품 목록
-- ============================================================
SELECT
    i.name_en   AS museum,
    a.title_en,
    a.title_ko,
    a.year_created,
    a.medium_en,
    a.source_id AS wikidata_id
FROM institutions i
LEFT JOIN artwork_ownerships ao ON ao.institution_id = i.id
LEFT JOIN artworks a            ON a.id = ao.artwork_id
ORDER BY i.name_en, a.year_created;


-- ============================================================
-- 3. Artwork count per country / 각 나라별 작품 갯수
-- ============================================================
SELECT
    i.country_code,
    COUNT(DISTINCT ao.artwork_id) AS artwork_count
FROM institutions i
LEFT JOIN artwork_ownerships ao ON ao.institution_id = i.id
GROUP BY i.country_code
ORDER BY artwork_count DESC;


-- ============================================================
-- 4. List of artworks per country / 각 나라별 속한 작품 목록
-- ============================================================
SELECT
    i.country_code,
    i.name_en   AS museum,
    a.title_en,
    a.title_ko,
    a.year_created,
    a.medium_en,
    a.source_id AS wikidata_id
FROM institutions i
LEFT JOIN artwork_ownerships ao ON ao.institution_id = i.id
LEFT JOIN artworks a            ON a.id = ao.artwork_id
ORDER BY i.country_code, i.name_en, a.year_created;
