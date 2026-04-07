package horosa.offline;

import boundless.types.ICache;
import boundless.types.cache.FilterCond;
import boundless.types.cache.FilterCond.MixOperator;
import boundless.types.cache.ICacheFactory;
import boundless.types.cache.SortCond;

import java.lang.reflect.Field;
import java.math.BigDecimal;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

public final class LocalCacheFactory implements ICacheFactory {
    private static final ConcurrentHashMap<String, LocalCache> CACHES = new ConcurrentHashMap<>();
    private String name;

    @Override
    public void build(String configPath) {
        // The Windows compatibility path keeps everything in-process.
    }

    @Override
    public ICache getCache() {
        String cacheName = (name == null || name.isBlank()) ? "default" : name;
        return CACHES.computeIfAbsent(cacheName, LocalCache::new);
    }

    @Override
    public void close() {
        // Keep caches alive for the lifetime of the backend process.
    }

    @Override
    public Boolean needMemCache() {
        return Boolean.FALSE;
    }

    @Override
    public Boolean needCompress() {
        return Boolean.FALSE;
    }

    @Override
    public Boolean needHystrix() {
        return Boolean.FALSE;
    }

    @Override
    public String factoryName() {
        return name;
    }

    @Override
    public void factoryName(String value) {
        this.name = value;
    }

    @Override
    public ICacheFactory spawnFactory(String value) {
        LocalCacheFactory spawned = new LocalCacheFactory();
        spawned.factoryName(value);
        return spawned;
    }

    static final class LocalCache implements ICache {
        private final String name;
        private final ConcurrentHashMap<String, Object> entries = new ConcurrentHashMap<>();
        private final CopyOnWriteArrayList<Map<String, Object>> docs = new CopyOnWriteArrayList<>();

        LocalCache(String name) {
            this.name = name;
        }

        @Override
        public void put(String key, Object value) {
            entries.put(key, deepCopyValue(value));
        }

        @Override
        public Object get(String key) {
            return deepCopyValue(entries.get(key));
        }

        @Override
        public boolean containsKey(String key) {
            return entries.containsKey(key);
        }

        @Override
        public long remove(String key) {
            return entries.remove(key) != null ? 1L : 0L;
        }

        @Override
        public void clear() {
            entries.clear();
            docs.clear();
        }

        @Override
        public void put(String key, Object value, int expireSeconds) {
            put(key, value);
        }

        @Override
        public void put(String key, Object value, long expireSeconds) {
            put(key, value);
        }

        @Override
        public void put(String key, Object value, int timeToIdleSeconds, int timeToLiveSeconds) {
            put(key, value);
        }

        @Override
        public void put(String key, Object value, long timeToIdleSeconds, long timeToLiveSeconds) {
            put(key, value);
        }

        @Override
        public Object getHash(String key, String field) {
            Object value = entries.get(key);
            if (value instanceof Map<?, ?> map) {
                return deepCopyValue(map.get(field));
            }
            return null;
        }

        @Override
        public void putHash(String key, String field, Object value) {
            Map<String, Object> map = ensureEntryMap(key);
            map.put(field, deepCopyValue(value));
            entries.put(key, map);
        }

        @Override
        public void putFieldValue(String key, String field, Object value) {
            putHash(key, field, value);
        }

        @Override
        public Map<String, Object> getMap(Object key) {
            Object value = entries.get(String.valueOf(key));
            if (value instanceof Map<?, ?> map) {
                return copyMap(map);
            }
            return null;
        }

        @Override
        public void setMap(Object key, Map<String, Object> value) {
            entries.put(String.valueOf(key), deepCopyValue(value));
        }

        @Override
        public void setMap(Object key, Map<String, Object> value, int expireSeconds) {
            setMap(key, value);
        }

        @Override
        public void add(Map<String, Object> value) {
            docs.add(copyMap(value));
        }

        @Override
        public void add(Map<String, Object> value, int expireSeconds) {
            add(value);
        }

        @Override
        public long size() {
            return entries.size() + docs.size();
        }

        @Override
        public long count(String field, String value) {
            return docs.stream().filter(doc -> Objects.equals(stringify(readField(doc, field)), value)).count();
        }

        @Override
        public long count(String field, long value) {
            return docs.stream().filter(doc -> Objects.equals(numberValue(readField(doc, field)), BigDecimal.valueOf(value))).count();
        }

        @Override
        public long countTotal() {
            return docs.size();
        }

        @Override
        public long count(FilterCond... conds) {
            return docs.stream().filter(doc -> matchesAll(doc, conds)).count();
        }

        @Override
        public long countValues(FilterCond... conds) {
            return count(conds);
        }

        @Override
        public List<Map<String, Object>> findValues(FilterCond... conds) {
            return findValues(Integer.MAX_VALUE, null, conds);
        }

        @Override
        public List<Map<String, Object>> findValues(int limit, FilterCond... conds) {
            return findValues(limit, null, conds);
        }

        @Override
        public List<Map<String, Object>> findValues(SortCond sort, FilterCond... conds) {
            return findValues(Integer.MAX_VALUE, sort, conds);
        }

        @Override
        public List<Map<String, Object>> findValues(int limit, SortCond sort, FilterCond... conds) {
            List<Map<String, Object>> results = new ArrayList<>();
            for (Map<String, Object> doc : docs) {
                if (!matchesAll(doc, conds)) {
                    continue;
                }
                results.add(copyMap(doc));
                if (results.size() >= limit) {
                    break;
                }
            }
            return results;
        }

        @Override
        public long remove(FilterCond... conds) {
            long removed = 0;
            List<Map<String, Object>> snapshot = new ArrayList<>(docs);
            for (Map<String, Object> doc : snapshot) {
                if (matchesAll(doc, conds) && docs.remove(doc)) {
                    removed += 1;
                }
            }
            return removed;
        }

        @Override
        public long remove(FilterCond cond) {
            return remove(new FilterCond[] {cond});
        }

        @Override
        public List<Map<String, Object>> getList(String field, Object value) {
            List<Map<String, Object>> results = new ArrayList<>();
            for (Map<String, Object> doc : docs) {
                if (Objects.equals(readField(doc, field), value)) {
                    results.add(copyMap(doc));
                }
            }
            return results;
        }

        @Override
        public void dropDataSet() {
            docs.clear();
        }

        @Override
        public Map<String, Object> getDistinct(String field) {
            Set<Object> values = new HashSet<>();
            for (Map<String, Object> doc : docs) {
                values.add(deepCopyValue(readField(doc, field)));
            }
            Map<String, Object> result = new HashMap<>();
            result.put(field, new ArrayList<>(values));
            return result;
        }

        @Override
        public void createIndex(String field, boolean unique) {
            // No-op for the in-memory compatibility cache.
        }

        @Override
        public long lpush(String key, String... values) {
            ArrayDeque<String> deque = ensureDeque(key);
            synchronized (deque) {
                for (String value : values) {
                    deque.addFirst(value);
                }
                return deque.size();
            }
        }

        @Override
        public String lpop(String key) {
            ArrayDeque<String> deque = ensureDeque(key);
            synchronized (deque) {
                return deque.pollFirst();
            }
        }

        @Override
        public long rpush(String key, String... values) {
            ArrayDeque<String> deque = ensureDeque(key);
            synchronized (deque) {
                for (String value : values) {
                    deque.addLast(value);
                }
                return deque.size();
            }
        }

        @Override
        public String rpop(String key) {
            ArrayDeque<String> deque = ensureDeque(key);
            synchronized (deque) {
                return deque.pollLast();
            }
        }

        @Override
        public List<String> lrang(String key, long start, long stop) {
            ArrayDeque<String> deque = ensureDeque(key);
            synchronized (deque) {
                List<String> values = new ArrayList<>(deque);
                int from = (int) Math.max(0, start);
                int toInclusive = stop < 0 ? values.size() - 1 : (int) Math.min(values.size() - 1, stop);
                if (values.isEmpty() || from > toInclusive) {
                    return Collections.emptyList();
                }
                return new ArrayList<>(values.subList(from, toInclusive + 1));
            }
        }

        @Override
        public Long llen(String key) {
            ArrayDeque<String> deque = ensureDeque(key);
            synchronized (deque) {
                return (long) deque.size();
            }
        }

        @Override
        public Long expire(String key, int seconds) {
            return entries.containsKey(key) ? 1L : 0L;
        }

        @Override
        public Long expireAt(String key, long timestamp) {
            return entries.containsKey(key) ? 1L : 0L;
        }

        @Override
        public long inc(String key, long delta) {
            synchronized (entries) {
                BigDecimal current = numberValue(entries.get(key));
                BigDecimal next = (current == null ? BigDecimal.ZERO : current).add(BigDecimal.valueOf(delta));
                entries.put(key, next.longValue());
                return next.longValue();
            }
        }

        @Override
        public long dec(String key, long delta) {
            return inc(key, -delta);
        }

        @Override
        public long inc(String key) {
            return inc(key, 1L);
        }

        @Override
        public long dec(String key) {
            return dec(key, 1L);
        }

        @Override
        public Long publish(String channel, String payload) {
            return 0L;
        }

        @Override
        public ICache spawnCache(String otherName) {
            return CACHES.computeIfAbsent(otherName, LocalCache::new);
        }

        private Map<String, Object> ensureEntryMap(String key) {
            Object existing = entries.get(key);
            if (existing instanceof Map<?, ?> map) {
                return copyMap(map);
            }
            return new HashMap<>();
        }

        private ArrayDeque<String> ensureDeque(String key) {
            Object existing = entries.get(key);
            if (existing instanceof ArrayDeque<?> deque) {
                @SuppressWarnings("unchecked")
                ArrayDeque<String> typed = (ArrayDeque<String>) deque;
                return typed;
            }
            ArrayDeque<String> created = new ArrayDeque<>();
            entries.put(key, created);
            return created;
        }

        private boolean matchesAll(Map<String, Object> doc, FilterCond... conds) {
            if (conds == null || conds.length == 0) {
                return true;
            }
            for (FilterCond cond : conds) {
                if (!matches(doc, cond)) {
                    return false;
                }
            }
            return true;
        }

        private boolean matches(Map<String, Object> doc, FilterCond cond) {
            if (cond == null) {
                return true;
            }
            FilterCond[] other = (FilterCond[]) reflect(cond, "otherCond");
            MixOperator mix = (MixOperator) reflect(cond, "mixOp");
            boolean current = matchesSingle(doc, cond);
            if (other == null || other.length == 0) {
                return current;
            }
            boolean rest = mix == MixOperator.Or ? false : true;
            for (FilterCond item : other) {
                boolean matched = matches(doc, item);
                if (mix == MixOperator.Or) {
                    rest = rest || matched;
                } else {
                    rest = rest && matched;
                }
            }
            return mix == MixOperator.Or ? (current || rest) : (current && rest);
        }

        private boolean matchesSingle(Map<String, Object> doc, FilterCond cond) {
            Object actual = readField(doc, cond.getField());
            Object expected = cond.getValue();
            String op = cond.getOp();
            if (op == null || op.isBlank() || "Eq".equalsIgnoreCase(op)) {
                return Objects.equals(actual, expected);
            }
            if ("Ne".equalsIgnoreCase(op)) {
                return !Objects.equals(actual, expected);
            }
            if ("Exists".equalsIgnoreCase(op)) {
                return actual != null;
            }
            if ("Like".equalsIgnoreCase(op)) {
                return actual != null && expected != null && stringify(actual).contains(stringify(expected));
            }
            if ("In".equalsIgnoreCase(op)) {
                if (expected instanceof Collection<?> items) {
                    for (Object item : items) {
                        if (Objects.equals(actual, item)) {
                            return true;
                        }
                    }
                    return false;
                }
                return Objects.equals(actual, expected);
            }
            BigDecimal actualNum = numberValue(actual);
            BigDecimal expectedNum = numberValue(expected);
            if (actualNum != null && expectedNum != null) {
                int compared = actualNum.compareTo(expectedNum);
                if ("Lt".equalsIgnoreCase(op)) {
                    return compared < 0;
                }
                if ("Lte".equalsIgnoreCase(op)) {
                    return compared <= 0;
                }
                if ("Gt".equalsIgnoreCase(op)) {
                    return compared > 0;
                }
                if ("Gte".equalsIgnoreCase(op)) {
                    return compared >= 0;
                }
            }
            return Objects.equals(actual, expected);
        }

        private Object readField(Map<String, Object> doc, String field) {
            if (field == null || field.isBlank()) {
                return null;
            }
            Object current = doc;
            for (String part : field.split("\\.")) {
                if (!(current instanceof Map<?, ?> map)) {
                    return null;
                }
                current = map.get(part);
            }
            return current;
        }

        private Object reflect(Object target, String fieldName) {
            try {
                Field field = target.getClass().getDeclaredField(fieldName);
                field.setAccessible(true);
                return field.get(target);
            } catch (ReflectiveOperationException ignored) {
                return null;
            }
        }

        private BigDecimal numberValue(Object value) {
            if (value instanceof Number number) {
                return new BigDecimal(number.toString());
            }
            if (value instanceof String text) {
                try {
                    return new BigDecimal(text);
                } catch (NumberFormatException ignored) {
                    return null;
                }
            }
            return null;
        }

        private String stringify(Object value) {
            return value == null ? "" : String.valueOf(value);
        }

        private Object deepCopyValue(Object value) {
            if (value instanceof Map<?, ?> map) {
                return copyMap(map);
            }
            if (value instanceof List<?> list) {
                List<Object> copy = new ArrayList<>();
                for (Object item : list) {
                    copy.add(deepCopyValue(item));
                }
                return copy;
            }
            if (value instanceof Set<?> set) {
                Set<Object> copy = new HashSet<>();
                for (Object item : set) {
                    copy.add(deepCopyValue(item));
                }
                return copy;
            }
            return value;
        }

        private Map<String, Object> copyMap(Map<?, ?> source) {
            Map<String, Object> copy = new HashMap<>();
            for (Map.Entry<?, ?> entry : source.entrySet()) {
                copy.put(String.valueOf(entry.getKey()), deepCopyValue(entry.getValue()));
            }
            return copy;
        }
    }
}
