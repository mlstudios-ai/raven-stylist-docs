variable "project" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "max_images" {
  description = "Number of images to retain in the repository"
  type        = number
  default     = 5
}
