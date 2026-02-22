package main

import (
	"context"
	"errors"
	"log"
	"os"
	"time"

	"sinker/db"

	"github.com/redis/go-redis/v9"
)

func main() {
	consumerName, _ := os.Hostname()
	log.Printf("Starting Sinker - Consumer: %s", consumerName)

	database := db.GetDBConnection()
	if database == nil {
		log.Fatal("CRITICAL: Failed to initialize database connection. Check DB_URL.")
	}
	defer database.Close()

	rdb := redis.NewClient(&redis.Options{
		Addr: os.Getenv("REDIS_ADDR"),
	})

	ctx := context.Background()
	stream := "alerts_stream"
	group := "group_persistence"

	err := rdb.XGroupCreateMkStream(ctx, stream, group, "0").Err()
	if err != nil {
		// Only log if the error is NOT that the group already exists
		if err.Error() != "BUSYGROUP Consumer Group name already exists" {
			log.Printf("Warning creating consumer group: %v", err)
		}
	}

	for {
		// Use AutoClaim to retrieve messages that were read but never Acknowledged
		claimed, _, err := rdb.XAutoClaim(ctx, &redis.XAutoClaimArgs{
			Stream:   stream,
			Group:    group,
			Consumer: consumerName,
			MinIdle:  30 * time.Second,
			Start:    "0-0",
		}).Result()

		if err != nil && !errors.Is(err, redis.Nil) {
			log.Printf("Error during AutoClaim: %v", err)
		}

		for _, msg := range claimed {
			if err := db.SaveAttackRecord(database, ctx, msg); err != nil {
				log.Printf("ERROR: Failed to persist claimed attack %s: %v", msg.ID, err)
			} else {
				log.Printf("Successfully persisted claimed attack: %v", msg.ID)
				rdb.XAck(ctx, stream, group, msg.ID)
			}
		}

		entries, err := rdb.XReadGroup(ctx, &redis.XReadGroupArgs{
			Group:    group,
			Consumer: consumerName,
			Streams:  []string{stream, ">"},
			Count:    5, 
			Block:    5 * time.Second,
		}).Result()

		if err != nil {
			if errors.Is(err, redis.Nil) {
				continue
			}
			log.Printf("Error reading from Redis Group: %v", err)
			time.Sleep(2 * time.Second)
			continue
		}

		for _, s := range entries {
			for _, msg := range s.Messages {
				if err := db.SaveAttackRecord(database, ctx, msg); err != nil {
					log.Printf("ERROR: Failed to persist new attack %s: %v", msg.ID, err)
				} else {
					log.Printf("Persisted new attack: %v", msg.ID)
					rdb.XAck(ctx, stream, group, msg.ID)
				}
			}
		}
	}
}