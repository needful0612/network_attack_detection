package main

import (
	"context"
	"log"
	"os"
	"time"

	"sinker/db"

	"github.com/redis/go-redis/v9"
)

func main() {
	consumerName, _ := os.Hostname()

	database := db.GetDBConnection()
	defer database.Close()

	rdb := redis.NewClient(&redis.Options{
		Addr: os.Getenv("REDIS_ADDR"),
	})

	ctx := context.Background()
	stream := "alerts_stream"
	group := "group_persistence"

	rdb.XGroupCreateMkStream(ctx, stream, group, "0")

	for {
		// AUTOCLAIM
		claimed, _, _ := rdb.XAutoClaim(ctx, &redis.XAutoClaimArgs{
			Stream:   stream,
			Group:    group,
			Consumer: consumerName,
			MinIdle:  30 * time.Second,
			Start:    "0-0",
		}).Result()

		for _, msg := range claimed {
			if err := db.SaveAttackRecord(database, ctx, msg); err == nil {
				log.Printf("Persisted claimed attack: %v", msg.ID)
				rdb.XAck(ctx, stream, group, msg.ID)
			}
		}

		// READ GROUP
		entries, err := rdb.XReadGroup(ctx, &redis.XReadGroupArgs{
			Group:    group,
			Consumer: consumerName,
			Streams:  []string{stream, ">"},
			Count:    1,
			Block:    5 * time.Second,
		}).Result()

		if err != nil {
			continue
		}

		for _, s := range entries {
			for _, msg := range s.Messages {
				if err := db.SaveAttackRecord(database, ctx, msg); err == nil {
					log.Printf("Persisted new attack: %v", msg.ID)
					rdb.XAck(ctx, stream, group, msg.ID)
				}
			}
		}
	}
}
