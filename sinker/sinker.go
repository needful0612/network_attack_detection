package main

import (
	"context"
	"database/sql"
	"errors"
	"log"
	"os"
	"os/signal"
	"sync"
	"strings"
	"syscall"
	"time"

	"sinker/db"

	"github.com/redis/go-redis/v9"
)

const (
	maxWorkers = 5
	stream     = "alerts_stream"
	group      = "group_persistence"
)

func main() {
	consumerName, _ := os.Hostname()
	log.Printf("Starting Sinker - Consumer: %s", consumerName)

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	
	ctx, exit := context.WithCancel(context.Background())
	defer exit()

	go func() {
		sig := <-sigChan
		log.Printf("Received signal %v, shutting down...", sig)
		exit()
	}()

	var database *sql.DB
    for {
        database = db.GetDBConnection()
        if database != nil {
            err := database.Ping()
            if err == nil {
                log.Printf("[+] Successfully connected to Database: %s", os.Getenv("DB_URL"))
                break
            }
            log.Printf("[!] Database reachable but Ping failed: %v. Retrying...", err)
        } else {
            log.Printf("[!] Failed to initialize DB driver. Retrying...")
        }

        select {
        case <-ctx.Done():
            return
        case <-time.After(5 * time.Second):
            // Continue retry loop
        }
    }
    defer database.Close()

	rdb := redis.NewClient(&redis.Options{
		Addr: os.Getenv("REDIS_ADDR"),
	})

	for {
        err := rdb.XGroupCreateMkStream(ctx, stream, group, "0").Err()
        if err == nil {
            log.Printf("[+] Consumer group '%s' created on stream '%s'", group, stream)
            break
        }

        if strings.Contains(err.Error(), "BUSYGROUP") {
            log.Printf("[*] Consumer group already exists, skipping creation.")
            break
        }

        log.Printf("[!] Redis/Stream not ready: %v. Retrying in 5s...", err)
        
        timer := time.NewTimer(5 * time.Second)
        select {
        case <-ctx.Done():
            timer.Stop()
            return
        case <-timer.C:
            // continue
        }
        timer.Stop()
    }

	msgChan := make(chan redis.XMessage, maxWorkers)
	var wg sync.WaitGroup

	for i := 1; i <= maxWorkers; i++ {
		wg.Add(1)
		go worker(ctx, i, &wg, msgChan, rdb, database)
	}
Loop:
	for {
		select {
		case <-ctx.Done():
			break Loop
		default:
			claimed, _, _ := rdb.XAutoClaim(ctx, &redis.XAutoClaimArgs{
				Stream:   stream,
				Group:    group,
				Consumer: consumerName,
				MinIdle:  30 * time.Second,
				Start:    "0-0",
			}).Result()

			for _, msg := range claimed {
				select {
				case msgChan <- msg:
				case <-ctx.Done():
					return // Stop trying to send if shutting down
				}
			}

			entries, err := rdb.XReadGroup(ctx, &redis.XReadGroupArgs{
				Group:    group,
				Consumer: consumerName,
				Streams:  []string{stream, ">"},
				Count:    int64(maxWorkers),
				Block:    2 * time.Second,
			}).Result()

			if err != nil {
				if !errors.Is(err, redis.Nil) && !errors.Is(err, context.Canceled) {
					log.Printf("Read error: %v", err)
				}
				continue
			}

			for _, s := range entries {
				for _, msg := range s.Messages {
					msgChan <- msg
				}
			}
		}
	}

	close(msgChan)
	log.Printf("Waiting for Workers to finish...")
	wg.Wait()
	log.Println("Sinker shutdown.")
	// /////
}

func worker(
	ctx context.Context,
	id int,
	wg *sync.WaitGroup,
	msgChan <-chan redis.XMessage,
	rdb *redis.Client,
	database *sql.DB,
) {
	defer wg.Done()
	for msg := range msgChan {
		//another context to ensure writing finish
		dbCtx, timeout := context.WithTimeout(context.Background(), 5*time.Second)

		if err := db.SaveAttackRecord(database, dbCtx, msg); err != nil {
			log.Printf("worker %d ERROR: %s: %v", id, msg.ID, err)
		} else {
			rdb.XAck(context.Background(), stream, group, msg.ID)
			log.Printf("Worker %d: Persisted %s", id, msg.ID)
		}

		timeout()
	}
}
