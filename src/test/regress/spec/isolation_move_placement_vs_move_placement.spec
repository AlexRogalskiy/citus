// we use 5 as the partition key value through out the test
// so setting the corresponding shard here is useful
setup
{
	SET citus.shard_count TO 2;
	SET citus.shard_replication_factor TO 1;
	CREATE TABLE test_move_table (x int, y int);
	SELECT create_distributed_table('test_move_table', 'x');

	SELECT get_shard_id_for_distribution_column('test_move_table', 5) INTO selected_shard_for_test_table;
}

teardown
{
	DROP TABLE test_move_table;
	DROP TABLE selected_shard_for_test_table;
}

session "s1"

// with copy all placements are cached
step "s1-load-cache"
{
	COPY test_move_table FROM PROGRAM 'echo "1,1\n2,2\n3,3\n4,4\n5,5"' WITH CSV;
}

step "s1-move-placement"
{
	SELECT master_move_shard_placement((SELECT * FROM selected_shard_for_test_table), 'localhost', 57637, 'localhost', 57638, 'force_logical');
}

session "s2"

step "s2-begin"
{
	BEGIN;
}

step "s2-move-placement"
{
	SELECT master_move_shard_placement((SELECT * FROM selected_shard_for_test_table), 'localhost', 57637, 'localhost', 57638, 'force_logical');
}

step "s2-commit"
{
	COMMIT;
}

step "s2-print-placements"
{
	SELECT
		nodename, nodeport, count(*)
	FROM
		pg_dist_shard_placement
	WHERE
		shardid IN (SELECT shardid FROM pg_dist_shard WHERE logicalrelid = 'test_move_table'::regclass)
	AND
		shardstate = 1
	GROUP BY
		nodename, nodeport;
}

// two concurrent shard moves on the same shard
// note that "s1-move-placement" errors out but that is expected
// given that "s2-move-placement" succeeds and the placement is
// already moved
permutation "s1-load-cache" "s2-begin" "s2-move-placement" "s1-move-placement" "s2-commit" "s2-print-placements"

// the same test without the load caches
permutation "s2-begin" "s2-move-placement" "s1-move-placement" "s2-commit" "s2-print-placements"
