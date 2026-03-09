{{/* broker */}}
{{- define "nids.redisAddr" -}}
{{- printf "%s-broker:6379" .Release.Name -}}
{{- end -}}

{{/* DB */}}
{{- define "nids.dbHost" -}}
{{- printf "%s-db" .Release.Name -}}
{{- end -}}