package db

import (
	"context"
	"database/sql"
	"encoding/json"
	"log"
	"os"

	_ "github.com/lib/pq"
	"github.com/redis/go-redis/v9"
)

func GetDBConnection() *sql.DB {
	db, err := sql.Open("postgres", os.Getenv("DB_URL"))
	if err != nil {
		log.Fatalf("Postgres connection error: %v", err)
	}
	return db
}

func SaveAttackRecord(db *sql.DB, ctx context.Context, msg redis.XMessage) error {
	var data map[string]interface{}
	if err := json.Unmarshal([]byte(msg.Values["data"].(string)), &data); err != nil {
		return err
	}

	_, err := db.Exec(`
		INSERT INTO alerts (time, src_ip, score, svm_score, kitnet_score) 
		VALUES (NOW(), $1, $2, $3, $4)`,
		data["ip"], data["score"], data["svm"], data["kitnet"])

	return err
}
